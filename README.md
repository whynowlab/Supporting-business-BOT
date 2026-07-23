# 지원사업 공고 텔레그램 봇

기업마당, 판판대로, 소상공인24 공고를 모아 회사 적합도를 판단하고 텔레그램으로 알립니다. GitHub Actions가 매일 08:00, 18:00 KST에 실행되며 수동 실행도 지원합니다.

이 버전은 [djfksjd/sole-search](https://github.com/djfksjd/sole-search)의 전수 수집, 수집 범위 공개, 상태 변경 감지, 근거 중심 판정 아이디어를 현재 봇 구조에 맞게 적용했습니다.

## 달라진 점

- 소상공인24 자체 공고와 통합 공고를 마지막 페이지까지 수집합니다.
- 기업마당, 판판대로, 소상공인24 간 동일 공고를 공고 ID 기준으로 합칩니다.
- 실행마다 출처별 `success`, `partial`, `failed`, `disabled` 상태와 수집 건수를 기록합니다.
- 수집 장애가 나면 GitHub Action 자체가 성공하더라도 텔레그램과 Action Summary에 누락 경고를 남깁니다.
- 신규 공고뿐 아니라 제목, 상태, 접수기간, 기관, 내용이 바뀐 공고도 `[변경: ...]`으로 다시 알립니다.
- 변경 공고와 마감 임박 공고부터 회차별로 처리하고, 남은 공고는 다음 실행으로 이월합니다.
- 텔레그램 제한을 넘는 결과는 공고 단위로 여러 메시지에 나눠 보내므로 뒤쪽 결과가 사라지지 않습니다.
- LLM 판정은 등급 A/B/C와 별도로 `확인됨`, `조건부`, `확인 필요`, `신청 불가`, `사업전환 후보` 중 하나를 표시합니다.
- 첨부파일 본문은 아직 자동 검증하지 않습니다. 웹 본문만으로 필수 요건이 끝까지 확인되지 않으면 `확인됨` 대신 `확인 필요`로 보수적으로 판정합니다.

## 수집 출처

| 출처 | 범위 | 장애 시 동작 |
|---|---|---|
| 기업마당 지원사업 | API 페이지 반복, 기본 최대 5페이지 | 0건 또는 페이지 상한 의심 시 경고 |
| 기업마당 행사 | API 페이지 반복, 기본 최대 5페이지 | 0건 또는 페이지 상한 의심 시 경고 |
| 판판대로 | 지원사업 공고, 기본 최대 5페이지 | 0건이면 경고, 비활성화 가능 |
| 소상공인24 | 자체 공고 전체 | 서버 고지 건수와 실제 수집 건수 비교 |
| 소상공인24 통합 | 타 기관 연계 공고 전체 | 서버 고지 건수와 실제 수집 건수 비교 |

## GitHub Secrets

저장소의 `Settings > Secrets and variables > Actions`에 등록합니다.

### 필수

| 이름 | 설명 |
|---|---|
| `BIZINFO_SUPPORT_KEY` | 기업마당 지원사업 API 인증키 |
| `BIZINFO_EVENT_KEY` | 기업마당 행사 API 인증키 |
| `TELEGRAM_BOT_TOKEN` | BotFather에서 발급한 봇 토큰 |
| `TELEGRAM_ALLOWED_CHAT_ID` | 알림을 받을 채팅 ID |

### 선택

| 이름 | 설명 | 기본값 |
|---|---|---|
| `GEMINI_API_KEY` | 상세 적합도 판정. 없으면 키워드 방식으로 대체 | 없음 |
| `BIZINFO_SEARCH_COUNT` | 기업마당 페이지당 요청 건수 | `100` |
| `BIZINFO_MAX_PAGES` | 기업마당 최대 페이지 수 | `5` |
| `FANFANDAERO_ENABLED` | 판판대로 사용 여부 | `true` |
| `FANFANDAERO_PAGE_UNIT` | 판판대로 페이지당 요청 건수 | `100` |
| `FANFANDAERO_MAX_PAGES` | 판판대로 최대 페이지 수 | `5` |
| `SBIZ24_ENABLED` | 소상공인24 사용 여부 | `true` |
| `SBIZ24_PAGE_SIZE` | 소상공인24 페이지당 요청 건수, 최대 200 | `100` |
| `SBIZ24_REQUEST_DELAY` | 소상공인24 페이지 사이 대기 시간, 최소 0.5초 | `0.5` |
| `MAX_PROGRAMS_PER_RUN` | 한 실행에서 상세 판정할 신규 공고 수, 변경 공고는 항상 우선 | `40` |
| `PROFILE_REGIONS` | 키워드 대체 판정의 허용 지역 JSON | `["전국"]` |
| `PROFILE_INTERESTS` | 키워드 대체 판정의 관심 분야 JSON | `[]` |
| `PROFILE_KEYWORDS` | 키워드 대체 판정의 포함 키워드 JSON | `[]` |
| `PROFILE_EXCLUDES` | 키워드 대체 판정의 제외 키워드 JSON | `[]` |
| `PROFILE_MIN_SCORE` | 키워드 대체 판정의 최소 점수 | `60` |

LLM 판정용 회사 정보는 현재 `src/company_profile.py`의 `COMPANY_PROFILE`을 사용합니다. 회사 정보가 바뀌면 이 파일도 함께 갱신해야 합니다.

## 상태 파일

GitHub Actions 캐시는 다음 파일을 실행 간 보존합니다.

- `data/notified_keys.json`: 이미 확인한 공고 키
- `data/program_state.json`: 변경 감지를 위한 직전 공고 스냅샷
- `data/decisions.jsonl`: 필터와 LLM 판정 로그
- `data/bot.db`: 정규화된 공고와 수집 실행 기록

출처가 `partial` 또는 `failed`이면 해당 출처의 이전 스냅샷을 보존해, 일시 장애 뒤 공고 전체가 신규로 오인되는 것을 막습니다.

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
python -m src.run_once
```

`python -m src.run_once`는 GitHub Actions와 같은 1회 실행 경로입니다. 텔레그램 키가 없으면 수집과 coverage 로그까지만 확인하고 메시지는 보내지 않습니다.
