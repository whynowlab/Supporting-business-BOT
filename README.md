# 기업마당 텔레그램 봇 (GitHub Actions 버전)

기업마당의 지원사업 및 행사 정보를 수집하여 텔레그램으로 알림을 보내주는 봇입니다.
**GitHub Actions**를 통해 매일 6시간마다 자동으로 실행됩니다.

## 🚀 설정 방법 (GitHub Secrets)

이 봇을 실행하려면 GitHub 저장소의 **Settings > Secrets and variables > Actions** 메뉴에서 다음 키들을 추가해야 합니다.

### 필수 키 (Required)
| 이름 | 설명 | 예시 |
|---|---|---|
| `BIZINFO_SUPPORT_KEY` | 기업마당 지원사업 API 인증키 | `kE9sDn...` |
| `BIZINFO_EVENT_KEY` | 기업마당 행사 API 인증키 | `aB3dEf...` |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 (@BotFather) | `123456:ABC-DEF...` |
| `TELEGRAM_ALLOWED_CHAT_ID` | 알림 받을 본인의 Chat ID | `987654321` |

### 선택 키 (Optional: 프로필 설정)
설정하지 않으면 기본값(전국/전체)으로 동작합니다.

| 이름 | 설명 | 형식(JSON) | 기본값 |
|---|---|---|---|
| `PROFILE_REGIONS` | 허용 지역 | `["서울", "경기"]` | `["전국"]` |
| `PROFILE_INTERESTS` | 관심 분야 | `["AI", "빅데이터"]` | `[]` |
| `PROFILE_KEYWORDS` | 포함 키워드(가산점) | `["창업", "수출"]` | `[]` |
| `PROFILE_EXCLUDES` | 제외 키워드 | `["교육", "세미나"]` | `[]` |
| `PROFILE_MIN_SCORE` | 최소 알림 점수 | 숫자 (예: `50`) | `60` |

---

## 로컬 실행 (테스트용)

1. **설치**
   ```bash
   pip install -r requirements.txt
   ```
2. **환경변수 설정**
   `.env.example` -> `.env` 복사 후 키 입력
3. **실행**
   ```bash
   python -m src.main       # 봇 서버 실행 (대화형)
   python -m src.run_once   # 1회 실행 테스트 (GitHub Actions와 동일)
   ```
