import os
import logging
import json
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, 
    filters, ConversationHandler
)
from datetime import datetime, timedelta
from .db import (
    get_connection, get_profile, update_profile, 
    upsert_program # used for save/dismiss logic if we track distinct table
)
from .filters import is_recommended, get_days_left

# Logger
logger = logging.getLogger(__name__)

# Constants for ConversationHandler
(
    SET_REGION,
    SET_INTERESTS,
    SET_INCLUDE,
    SET_EXCLUDE,
    SET_MIN_SCORE,
    SET_NOTIFY_ENABLED,
    SET_NOTIFY_TIME,
    SET_DUE_THRESHOLD
) = range(8)

ALLOWED_CHAT_ID = os.getenv("TELEGRAM_ALLOWED_CHAT_ID")

def restricted(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        # Check against string or int
        allowed = str(ALLOWED_CHAT_ID)
        if str(chat_id) != allowed and str(user_id) != allowed:
            await update.message.reply_text("⛔ 승인되지 않은 사용자입니다.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
    await update.message.reply_text(
        "👋 기업마당 봇입니다.\n\n"
        "명령어 목록:\n"
        "/digest - 추천 목록\n"
        "/support - 지원사업 추천\n"
        "/events - 행사 추천\n"
        "/due - 마감 임박\n"
        "/profile - 프로필 조회\n"
        "/set_profile - 프로필 설정\n"
        "/health - 상태 확인"
    )

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ingestion_runs ORDER BY run_at DESC LIMIT 5")
    rows = cursor.fetchall()
    conn.close()
    
    msg = "🏥 **시스템 상태**\n\n"
    for r in rows:
        err = f"(Error: {r['error']})" if r['error'] else "✅"
        msg += f"[{r['run_at'][:16]}] {r['kind']}: {r['fetched_count']} fetched, {r['new_count']} new {err}\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- Helper for list formatting ---
async def send_chunked(update: Update, text: str):
    # Split by chunks of 4000
    if len(text) <= 4000:
        await update.message.reply_text(text, parse_mode=None) # plain text to avoid markdown errors or disable preview
        return
        
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i+4000], parse_mode=None)

def format_program_list(programs, profile, title="목록"):
    if not programs:
        return f"📭 {title}: 결과가 없습니다."
        
    msg = f"📢 **{title} ({len(programs)}건)**\n\n"
    for p in programs:
        # Check recommendation
        # We might pass pre-calculated reasons if available, else calc on fly
        rec, score, reasons = is_recommended(p, profile)
        
        icon = "📅" if p['kind'] == 'event' else "💰"
        
        msg += f"{icon} [{score}점] {p['title']}\n"
        if p.get('apply_end_at'):
            msg += f"⏳ 마감: {p['apply_end_at']}\n"
        if reasons:
            msg += f"💡 {', '.join(reasons)}\n"
        msg += f"🔗 {p['url']}\n"
        msg += f"👉 /save_{p['program_key'].replace(':','_')} | /dismiss_{p['program_key'].replace(':','_')}\n\n"
        
    return msg

# --- List Handlers ---
async def list_programs(update: Update, context: ContextTypes.DEFAULT_TYPE, kind=None, due_only=False):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return

    conn = get_connection()
    cursor = conn.cursor()
    profile = get_profile()
    
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
    
    query = "SELECT * FROM programs WHERE 1=1"
    params = []
    
    if kind:
        query += " AND kind = ?"
        params.append(kind)
        
    # Filtering handled in Python or SQL?
    # Logic: Get candidates -> Filter/Score -> Sort -> Slice
    # Since we need scoring, better to fetch valid candidates then sort in python.
    # Filter out dismissed?
    # For now fetch recent active items.
    
    # "Recent" definition for general list? OR "All valid"?
    # Usually lists show "Active" items (not closed).
    today = datetime.now().strftime("%Y-%m-%d")
    # For support, apply_end_at >= today or null
    # For event, event_end_at >= today or null (or apply_end_at)
    
    # We can fetch all that are not clearly closed in past.
    # Logic: apply_end_at IS NULL OR apply_end_at >= today
    query += f" AND (apply_end_at IS NULL OR apply_end_at >= '{today}')"
    
    # Also sort by created_at desc for general list? Or Score?
    # PRD assumes recommendation for /digest, /support.
    # "/support [n] : 지원사업 추천 n개" -> implies scoring.
    
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    # Check dismissed
    # Need user_actions. 
    # Let's simple check: exclude if action='dismissed'
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT program_key FROM user_actions WHERE action='dismissed'")
    dismissed = set(r[0] for r in c.fetchall())
    conn.close()
    
    candidates = []
    for r in rows:
        if r['program_key'] in dismissed:
            continue
            
        rec, score, reasons = is_recommended(r, profile)
        
        if due_only:
            # Check if due <= threshold
            days = get_days_left(r)
            if days is not None and days <= profile['due_days_threshold'] and days >= 0:
                pass
            else:
                continue
                
        # If standard recommendation command, must meet min_score?
        # PRD: "/support [n] : 지원사업 추천" -> yes.
        # But if user wants to see *all* due?
        # Let's apply min_score filter generally for recommendation info.
        # But for /due, maybe loose score?
        # PRD 8.2 says "score >= min_score일 때 추천 목록에 포함".
        # So yes, filter by score.
        
        if score >= profile['min_score']:
            candidates.append({
                **r, 'score': score, 'reasons': reasons
            })
            
    # Sort
    if due_only:
        # Sort by days left asc
        candidates.sort(key=lambda x: get_days_left(x) if get_days_left(x) is not None else 999)
    else:
        # Sort by score desc, then date
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
    top_n = candidates[:limit]
    
    await send_chunked(update, format_program_list(top_n, profile, title=f"추천 {'마감임박' if due_only else ''} ({kind or '전체'})"))

async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_programs(update, context, kind=None)

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_programs(update, context, kind='support')

async def cmd_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_programs(update, context, kind='event')

async def cmd_due(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_programs(update, context, kind=None, due_only=True)

async def cmd_due_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_programs(update, context, kind='support', due_only=True)

async def cmd_due_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_programs(update, context, kind='event', due_only=True)

# --- Action Handlers (Save/Dismiss) ---
# Since key structure is kind:seq, and telegram commands can't have ':', 
# We use underscores in link and replace back.
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
        
    msg = update.message.text
    # /save_support_123 or /save support:123 if typed manually?
    # PRD says "/save <id>". 
    # Let's support both /save <id> and /save_id
    
    cmd, *args = msg.split()
    action = None
    if "save" in cmd:
        action = "saved"
    elif "dismiss" in cmd:
        action = "dismissed"
    else:
        return
        
    # Extract key
    key = None
    if "_" in cmd:
        # /save_program_key
        parts = cmd.split("_", 1)
        if len(parts) > 1:
            key = parts[1].replace("_", ":", 1) # Support:123 -> support_123 -> support:123. 
            # Wait, 123 might have underscores? Bizinfo IDs are usually numeric or alphanumeric.
            # "support:123" -> "support_123". "event:ABC" -> "event_ABC".
            # Be careful if ID has ":".
            # Assuming kind is "support" same as "support".
            pass
    elif args:
        key = args[0]
        
    if not key:
        return
        
    # Logic
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT OR REPLACE INTO user_actions (program_key, action, created_at) VALUES (?, ?, ?)", 
                  (key, action, datetime.now().isoformat()))
        conn.commit()
        await update.message.reply_text(f"✅ {action}: {key}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        conn.close()

# --- Conversation Flow for Profile ---
async def set_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return ConversationHandler.END
    await update.message.reply_text("프로필 설정을 시작합니다.\n\n허용 지역을 입력하세요.\n(예: 서울, 경기 / 또는 '전국')")
    return SET_REGION

async def set_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    regions = [r.strip() for r in text.replace(" ", "").split(",")]
    context.user_data['region_allow'] = json.dumps(regions, ensure_ascii=False)
    await update.message.reply_text("관심 분야 키워드를 입력하세요.\n(쉼표 구분, 예: AI, 빅데이터, 수출)")
    return SET_INTERESTS

async def set_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    items = [r.strip() for r in text.replace(" ", "").split(",") if r.strip()]
    context.user_data['interests'] = json.dumps(items, ensure_ascii=False)
    await update.message.reply_text("포함할 키워드(가산점)를 입력하세요.\n(쉼표 구분)")
    return SET_INCLUDE

async def set_include(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    items = [r.strip() for r in text.replace(" ", "").split(",") if r.strip()]
    context.user_data['include_keywords'] = json.dumps(items, ensure_ascii=False)
    await update.message.reply_text("제외할 키워드(필터)를 입력하세요.\n(쉼표 구분)")
    return SET_EXCLUDE

async def set_exclude(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    items = [r.strip() for r in text.replace(" ", "").split(",") if r.strip()]
    context.user_data['exclude_keywords'] = json.dumps(items, ensure_ascii=False)
    await update.message.reply_text("최소 알림 점수(0~100)를 입력하세요. (기본 60)")
    return SET_MIN_SCORE

async def set_min_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        score = int(update.message.text)
        context.user_data['min_score'] = score
        await update.message.reply_text("알림을 받으시겠습니까? (1: 예, 0: 아니오)")
        return SET_NOTIFY_ENABLED
    except ValueError:
        await update.message.reply_text("숫자로 입력해주세요.")
        return SET_MIN_SCORE

async def set_notify_enabled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text)
        context.user_data['notify_enabled'] = 1 if val > 0 else 0
        await update.message.reply_text("알림 시각을 입력하세요 (HH:MM, KST). 예: 08:30")
        return SET_NOTIFY_TIME
    except:
        await update.message.reply_text("1 또는 0을 입력하세요.")
        return SET_NOTIFY_ENABLED

async def set_notify_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # Basic validation
    if ":" not in text:
        text = "08:30"
    context.user_data['notify_time_kst'] = text
    await update.message.reply_text("마감 임박 기준일(D-Day)을 입력하세요. (기본 7)")
    return SET_DUE_THRESHOLD

async def set_due_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text)
        context.user_data['due_days_threshold'] = days
        
        # Save
        update_profile(context.user_data)
        
        await update.message.reply_text("✅ 프로필 설정이 완료되었습니다!")
        return ConversationHandler.END
    except:
         await update.message.reply_text("숫자를 입력하세요.")
         return SET_DUE_THRESHOLD

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("설정을 취소했습니다.")
    return ConversationHandler.END

# --- Profile View ---
async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
    p = get_profile()
    msg = f"👤 **프로필 설정**\n\n"
    msg += f"허용지역: {p['region_allow']}\n"
    msg += f"관심분야: {p['interests']}\n"
    msg += f"포함키워드: {p['include_keywords']}\n"
    msg += f"제외키워드: {p['exclude_keywords']}\n"
    msg += f"최소점수: {p['min_score']}\n"
    msg += f"알림: {'ON' if p['notify_enabled'] else 'OFF'} ({p['notify_time_kst']})\n"
    msg += f"마감임박: D-{p['due_days_threshold']}\n"
    await update.message.reply_text(msg)

# --- Mute/Unmute ---
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
    update_profile({"notify_enabled": 0})
    await update.message.reply_text("🔕 알림이 꺼졌습니다.")

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != str(ALLOWED_CHAT_ID):
        return
    update_profile({"notify_enabled": 1})
    await update.message.reply_text("🔔 알림이 켜졌습니다.")

# --- Setup Application ---
def create_app(token):
    app = ApplicationBuilder().token(token).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("events", cmd_events))
    app.add_handler(CommandHandler("due", cmd_due))
    app.add_handler(CommandHandler("due_support", cmd_due_support))
    app.add_handler(CommandHandler("due_events", cmd_due_events))
    
    # Conversation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("set_profile", set_profile_start)],
        states={
            SET_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_region)],
            SET_INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_interests)],
            SET_INCLUDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_include)],
            SET_EXCLUDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_exclude)],
            SET_MIN_SCORE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_min_score)],
            SET_NOTIFY_ENABLED: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_notify_enabled)],
            SET_NOTIFY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_notify_time)],
            SET_DUE_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_due_threshold)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)
    
    # Action Handlers (Regex for save/dismiss commands with underscores)
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    
    # Generic save/dismiss handling via MessageHandler or explicit CommandHandler with regex?
    # CommandHandler usually takes a string.
    # To handle /save_foo_bar, we can use `MessageHandler(filters.Regex(r'^/(save|dismiss)_'), ...)`
    app.add_handler(MessageHandler(filters.Regex(r'^/(save|dismiss)'), action_handler))
    
    return app
