# SSAFY 급식봇

전기부산 점심 메뉴를 Mattermost **간식먹고노라라** 채널에 **평일 11:00** 자동으로 보냅니다.

## 구조

```
lunchbot/
  __main__.py   CLI + 파이프라인 (메뉴 조회 → 사진 채우기 → 전송)
  config.py     .env 설정 (Settings)
  models.py     StationMenu / DayMenu, 시간 헬퍼
  welplan.py    메뉴 원본 + 당일 사진 1차 소스
  welstory.py   사진 폴백 1 (웰스토리플러스 API)
  bobssafy.py   사진 폴백 2 (Streamlit 페이지, Playwright)
  message.py    Mattermost 마크다운 (사진 크기 통일)
  notify.py     Mattermost 전송 (웹훅 / API 토큰)
```

사진은 **Welplan live API → BOB SSAFY → 웰스토리 API** 순으로 채우고, 요리 사진 대신
플레이스홀더가 걸린 코너는 사진 없이 보냅니다. 소스마다 원본 크기가 달라서 표에 넣을 때는
`message.py`의 `IMAGE_WIDTH`/`IMAGE_HEIGHT`(기본 240×180)로 전부 같은 크기로 맞춥니다.

## 자동 전송 (Windows)

PC가 켜져 있고 로그인한 상태면, 작업 스케줄러가 평일 11시에 보냅니다.

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\SSAFY\ssafy-lunch-bot\scripts\install-task.ps1
```

- 작업 이름: `SSAFYLunchBot`
- 로그: `C:\Users\SSAFY\ssafy-lunch-bot\logs\lunch.log`

## GitHub Actions

저장소를 GitHub에 올리고 Secrets에 `MATTERMOST_WEBHOOK_URL`만 넣으면, PC를 켜두지 않아도
평일 11:00(KST)에 전송됩니다.

## 수동 확인

```powershell
pip install -r requirements.txt
python -m playwright install chromium

python -m lunchbot --dry-run          # 보낼 메시지만 출력
python -m lunchbot --test-welstory    # 웰스토리 사진 URL만 확인
python -m lunchbot --test-bobssafy    # BOB SSAFY 사진 URL만 확인
python -m lunchbot --list-restaurants # Welplan 식당 코드 검색
python -m lunchbot                    # 실제 전송
python -m pytest tests -q
```

설정은 `.env.example` 를 `.env` 로 복사해서 채우세요.
