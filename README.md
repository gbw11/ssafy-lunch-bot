# SSAFY 급식봇

전기부산 점심 메뉴를 Mattermost **간식먹고노라라** 채널에 **평일 11:00** 자동으로 보냅니다.

## 자동 전송 (Windows)

PC가 켜져 있고 로그인한 상태면, 작업 스케줄러가 평일 11시에 보냅니다.

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\SSAFY\ssafy-lunch-bot\scripts\install-task.ps1
```

- 작업 이름: `SSAFYLunchBot`
- 로그: `C:\Users\SSAFY\ssafy-lunch-bot\logs\lunch.log`

## GitHub Actions

저장소를 GitHub에 올리고 Secrets에 `MATTERMOST_WEBHOOK_URL`만 넣으면, PC를 켜두지 않아도 평일 11:00(KST)에 전송됩니다.

## 수동 확인

```powershell
python -m lunchbot --dry-run
python -m lunchbot
```
