# SSAFY 급식봇

전기부산 점심 메뉴를 Mattermost **간식먹고노라라** 채널에 자동으로 보냅니다.

## 구조

```
lunchbot/
  __main__.py   CLI + 파이프라인 (메뉴 조회 → 사진 채우기 → 전송)
  config.py     .env 설정 (Settings)
  models.py     StationMenu / DayMenu, 시간 헬퍼
  welplan.py    메뉴 원본 + 당일 사진 1차 소스
  welstory.py   사진 폴백 1 (웰스토리플러스 API)
  mealcloud.py  사진 폴백 2 (welstory-meal.cloud JSON API)
  message.py    Mattermost 마크다운 (사진 크기 통일)
  notify.py     Mattermost 전송 (웹훅 / API 토큰)
```

사진은 **Welplan live API → welstory-meal.cloud → 웰스토리 API** 순으로 채우고, 요리 사진 대신
플레이스홀더가 걸린 코너는 사진 없이 보냅니다. welstory-meal.cloud 는 코너명(`courseName`)이
Welplan 과 어긋나는 날이 있고 코너 순서도 날마다 달라서, 코너명이나 순서가 아니라 **메뉴명**으로
짝지웁니다(`models.menu_key`). 소스마다 원본 크기가 달라서 표에 넣을 때는
`message.py`의 `IMAGE_WIDTH`/`IMAGE_HEIGHT`(기본 240×180)로 전부 같은 크기로 맞춥니다.

## 자동 전송 (GitHub Actions)

GitHub 자체 cron은 지연이 심해서 쓰지 않습니다. 외부 cron(cron-job.org)이 **평일
10:39 KST**에 `daily-lunch.yml`을 `workflow_dispatch`로 트리거하고, 봇이 점심 사진이
올라올 때까지(최대 `PHOTO_WAIT_MINUTES`분) 기다렸다가 대개 **11:00 전후**에 전송합니다.

저장소 Secrets에 `MATTERMOST_WEBHOOK_URL`만 넣으면 동작하고, 사진 폴백까지 쓰려면
`WELLSTORY_USERNAME`/`WELLSTORY_PASSWORD`도 넣어 주세요. 나머지 설정은 워크플로
파일의 `env` 블록에 있습니다.

## 수동 확인

```powershell
pip install -r requirements.txt

python -m lunchbot --dry-run          # 보낼 메시지만 출력
python -m lunchbot --test-welstory    # 웰스토리 사진 URL만 확인
python -m lunchbot --test-mealcloud   # welstory-meal.cloud 사진 URL만 확인
python -m lunchbot --list-restaurants # Welplan 식당 코드 검색
python -m lunchbot                    # 실제 전송
python -m pytest tests -q
```

설정은 `.env.example` 를 `.env` 로 복사해서 채우세요.

## 사진 타이밍

웰스토리는 코너별 실제 배식 사진을 배식 직전(대개 10:30 전후)에 올립니다. 그전까지
점심 메뉴에 걸려 있는 이미지는 전부 같은 플레이스홀더 JPEG입니다. 같은 시각에 조식
사진은 이미 새벽에 올라와 있으므로, 끼니(`mealTimeId`)를 구분하지 않으면 점심 글에
조식 사진이 실립니다. `welplan.course_photos` 가 중식(`mealTimeId=2`)만 남기고,
`PHOTO_WAIT_MINUTES` 동안 사진이 올라오길 기다린 뒤 그래도 없으면 사진 없이 보냅니다.
