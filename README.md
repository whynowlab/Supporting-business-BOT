# 기업마당 텔레그램 봇 (1인용)

기업마당의 지원사업 및 행사 정보를 수집하여 SQLite에 저장하고, 사용자 프로필에 맞춰 텔레그램으로 알림을 보내주는 봇입니다.

## 목표
- 기업마당 지원사업/행사 정보 통합 수집
- 개인화된 필터링 및 알림 제공
- 일일 추천(Digest) 및 실시간 수집

## 요구사항
- Python 3.11 이상
- SQLite (Python 내장)

## 설정 및 실행

1. **저장소 클론**
2. **패키지 설치**
   ```bash
   pip install -r requirements.txt
   ```
3. **환경변수 설정**
   - `.env.example`을 `.env`로 복사합니다.
   - API 키와 텔레그램 토큰을 입력합니다.
   ```bash
   cp .env.example .env
   ```
4. **실행**
   ```bash
   python -m src.main
   ```

## 도커 실행

1. **빌드**
   ```bash
   docker-compose build
   ```
2. **실행**
   ```bash
   docker-compose up -d
   ```

## 프로젝트 구조
- `src/`: 소스 코드
  - `main.py`: 시작점
  - `bizinfo_client.py`: API 클라이언트
  - `db.py`: 데이터베이스 처리
  - `scheduler.py`: 스케줄러
  - `telegram_bot.py`: 봇 로직
- `tests/`: 유닛 테스트
