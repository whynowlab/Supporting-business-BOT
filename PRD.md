# PRD.md — 기업마당 지원사업/행사 텔레그램 봇 (KR-only, Single-user)

## 0. 목표
- 기업마당 **지원사업정보 API + 행사정보 API**를 주기적으로 수집하여
- 단일 사용자(본인)에게 텔레그램으로 **추천/마감임박/저장 목록**을 제공한다.
- 운영 형태: 서버/PC/VPS 어디서든 실행 가능하되, MVP는 **Python + python-telegram-bot(롱폴링) + APScheduler + SQLite**로 완결.

---

## 1. 범위(Scope)

### 1.1 MVP 포함
1) 기업마당 API 2종 수집
   - 지원사업정보 API
   - 행사정보 API
2) 데이터 정규화(공통 스키마) + SQLite 저장
3) 단일 회사 프로필(비민감 선호/조건) 저장/수정
4) 매칭(하드필터 + 점수화) + 추천 사유 표시
5) 텔레그램 명령어 기반 UX
6) 자동 알림
   - 데일리 다이제스트(추천)
   - 마감임박 알림(옵션)
7) 단일 사용자 보호(allowlist chat_id)

### 1.2 MVP 제외
- 다중 사용자/팀 공유/결제
- 신청서 자동 작성/제출
- 크롤링(기업마당 API만 사용)

---

## 2. 데이터 소스

### 2.1 지원사업정보 API
- Endpoint: `https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do`
- 인증키: `crtfcKey`
- 응답: `dataType=json` 우선, 불가 시 RSS/XML 폴백 파싱
- 필터 파라미터(선택): `hashtags`, `searchLclasId`, `pageUnit/pageIndex` 또는 `searchCnt`

### 2.2 행사정보 API
- Endpoint: `https://www.bizinfo.go.kr/uss/rss/bizinfoEventApi.do`
- 인증키: `crtfcKey`
- 응답: `dataType=json` 우선, 불가 시 RSS/XML 폴백 파싱
- 필터 파라미터(선택): `hashtags`, `searchLclasId`, `pageUnit/pageIndex` 또는 `searchCnt`

---

## 3. 실행/구성(권장 스택)
- Python 3.11+
- Bot: `python-telegram-bot` (long polling)
- Scheduler: `APScheduler`
- Storage: `SQLite` (단일 사용자 최적)
- 배포: 로컬 상시 실행 / VPS / Docker (선택)

---

## 4. 환경변수(.env)
- `BIZINFO_SUPPORT_KEY` : 지원사업 API crtfcKey
- `BIZINFO_EVENT_KEY` : 행사 API crtfcKey
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_ID` : 단일 사용자 chat_id (allowlist)

---

## 5. 텔레그램 UX (명령어)

### 5.1 공통
- `/start` : 사용 안내 + 상태
- `/health` : 마지막 수집 시각, 최근 수집 건수/에러
- `/set_profile` : 프로필 설정(마법사 또는 인자 입력)
- `/profile` : 프로필 조회
- `/mute` `/unmute` : 자동알림 on/off

### 5.2 추천/조회
- `/digest [n]` : 추천(지원+행사 합산) n개 (기본 10)
- `/support [n]` : 지원사업 추천 n개
- `/events [n]` : 행사 추천 n개
- `/due [days]` : 마감임박(지원+행사 합산) (기본 7)
- `/due_support [days]` : 지원사업 마감임박
- `/due_events [days]` : 행사 접수 마감임박

### 5.3 액션
- `/save <id>` : 저장(지원/행사 공통 id)
- `/dismiss <id>` : 제외(지원/행사 공통 id)
- `/saved` : 저장 목록
- `/dismissed` : 제외 목록
- `/open <id>` : 원문 링크 출력

> id 충돌 방지: 내부적으로 `program_key = "{kind}:{source_id}"` 형태를 사용한다.
> - kind = support | event
> - source_id = 기업마당 item의 seq(문서상 ID)

---

## 6. 데이터 모델(정규화)

### 6.1 공통 정규화 엔티티: programs
**Table: `programs`**
- `program_key` (PK) : `support:{seq}` 또는 `event:{seq}`
- `kind` : `support` | `event`
- `source` : `bizinfo`
- `seq` : 원문 ID
- `title`
- `summary_raw` : 원문 개요/설명(가능한 경우)
- `agency` : 소관/출처기관(가능한 경우)
- `category_l1` : 대분류(가능한 경우)
- `region_raw` : 지역/해시태그 원문(가능한 경우)
- `apply_period_raw` : 신청/접수 기간 원문 문자열
- `apply_start_at` (nullable)
- `apply_end_at` (nullable)
- `event_period_raw` : (행사만) 행사 기간 원문
- `event_start_at` (nullable)
- `event_end_at` (nullable)
- `url`
- `created_at_source` (nullable) : 공고 게시/등록일(가능할 때)
- `updated_at_source` (nullable)
- `ingested_at` : 수집 시각

### 6.2 프로필: company_profile (단일 row)
**Table: `company_profile`**
- `id` (PK, 항상 1)
- `region_allow` : JSON array (예: ["전국","서울","경기","인천"])
- `interests` : JSON array (예: ["기술","R&D","수출"])
- `include_keywords` : JSON array
- `exclude_keywords` : JSON array
- `min_score` : int (기본 60)
- `notify_enabled` : bool
- `notify_time_kst` : string (기본 "08:30")
- `due_days_threshold` : int (기본 7)

### 6.3 사용자 액션: user_actions
**Table: `user_actions`**
- `program_key`
- `action` : `saved` | `dismissed`
- `created_at`

### 6.4 수집 로그: ingestion_runs
**Table: `ingestion_runs`**
- `run_at`
- `kind` : `support` | `event`
- `fetched_count`
- `new_count`
- `updated_count`
- `error` (nullable)

---

## 7. 수집(인제션) 요구사항

### 7.1 스케줄 (KST)
- 기본: 하루 2회 수집 (예: 08:00, 18:00 KST)
- 데일리 다이제스트 발송: 08:30 KST (notify_enabled일 때)

### 7.2 동작
- 지원/행사 각각 API 호출 → item 리스트 확보
- JSON 우선, 실패 시 RSS/XML 파싱 폴백
- `program_key` 기준 upsert
- 변경 감지: 주요 필드 해시 또는 `updated_at_source`가 있으면 활용
- 장애 내성:
  - 재시도(최대 3회, backoff)
  - support 실패해도 event 수집은 진행(독립 실행)

---

## 8. 매칭(추천) 로직

### 8.1 하드 필터(공통)
- 제외 키워드(exclude_keywords)가 `title/summary/agency/url`에 포함되면 제외
- region_allow가 설정되어 있고, region_raw/hashtags 기반으로 명확히 배제 가능하면 제외
- (옵션) apply_end_at이 과거이면 제외(파싱 가능할 때만)

### 8.2 점수화(공통)
- 관심분야(interests) 관련 키워드가 `title/summary/category_l1`에 매칭: +25
- include_keywords 매칭(1개당 +10, 최대 +30)
- 마감임박(<= due_days_threshold): +15
- 기본 가산(정보량 최소라도 노출): +5
- 최종 score 0~100 클램프
- `score >= min_score`일 때 추천 목록에 포함

### 8.3 “추천 사유” 출력(필수)
추천 카드에 사유 2~4개를 항상 포함(템플릿 기반, 추측 금지):
- “키워드 매칭: …”
- “관심분야 일치: …”
- “마감 임박: D-…”
- “지역 조건 충족: …”

---

## 9. 마감임박 정의(지원 vs 행사)

### 9.1 지원사업
- `apply_period_raw`에서 종료일 파싱 → `apply_end_at`
- 오늘(KST) 기준 D-day 계산

### 9.2 행사
- **접수 마감** 기준: `apply_period_raw`(예: rceptPd 유사 필드)에서 종료일 파싱 → `apply_end_at`
- 행사 자체 일정은 `event_period_raw`로 별도 저장하되, “마감임박”은 접수 마감 기준을 우선한다.

> 날짜 파싱 실패 시: raw 문자열만 저장하고, due 판단은 스킵(크래시 금지).

---

## 10. 텔레그램 카드 포맷(출력)

### 10.1 리스트 카드(추천/마감임박 공통)
- `[점수][지원사업|행사][카테고리] 제목`
- `기간: YYYY-MM-DD ~ YYYY-MM-DD` (없으면 원문)
- `기관: ...`
- `사유: ... (2~4개)`
- `링크: ...`
- `액션: /save <program_key>  /dismiss <program_key>  /open <program_key>`

### 10.2 메시지 분할
- 텔레그램 메시지 길이 제한을 고려해 chunking 전송
- 링크 미리보기 off 기본

---

## 11. 기본값(프로필 미설정 시)
- region_allow = ["전국"]
- interests = []
- include_keywords = []
- exclude_keywords = []
- min_score = 60
- due_days_threshold = 7
- notify_enabled = true
- notify_time_kst = "08:30"

---

## 12. 수용 기준(Acceptance Criteria)
- (AC1) 지원사업/행사 API를 각각 호출해 `programs`에 저장된다.
- (AC2) /support, /events, /digest가 정상 동작하고 추천 사유가 표시된다.
- (AC3) /due_support, /due_events, /due가 종료일 파싱 가능한 항목에 대해 D-day 기준으로 동작한다.
- (AC4) /save, /dismiss가 저장되며 /saved, /dismissed에 반영된다.
- (AC5) allowlisted chat_id 외 접근 시 명령을 거부한다.
- (AC6) 스케줄러가 지정 시각에 수집/다이제스트를 수행한다(자동알림 on일 때).

---

## 13. 구현 산출물(Repo Deliverables)
- `PRD.md`
- `README.md` (로컬 실행 + Docker 실행)
- `.env.example`
- `requirements.txt`
- `src/`
  - `main.py` (엔트리포인트)
  - `bizinfo_client.py` (지원/행사 API 호출 + JSON/XML 파싱)
  - `normalizer.py` (공통 모델 변환)
  - `due_parser.py` (기간 문자열 파싱)
  - `filters.py` (키워드/지역/스코어)
  - `db.py` (SQLite schema + upsert)
  - `telegram_bot.py` (명령어 핸들러 + 출력/청크)
  - `scheduler.py` (APScheduler 잡 등록)
- `tests/`
  - `test_due_parser.py`
  - `test_scoring.py`
  - `test_actions_save_dismiss.py`
