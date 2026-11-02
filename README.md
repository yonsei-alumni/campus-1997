# 신촌 캠퍼스 1997 — 연세 캠퍼스 산책 (3D)

1997년 5월, 신촌 연세대학교 캠퍼스를 1인칭으로 걸어 다니는 웹 3D 게임입니다.
정문에서 출발해 백양로를 따라 걸으면서 중앙도서관, 학생회관, 독수리상, 백주년기념관, 옛 노천극장,
언더우드관을 둘러볼 수 있습니다. 랜드마크 앞에서 **E** 를 누르면 `reference.pdf` 에 실린 그 시절 사진과 이야기가 담긴
“추억 카드”가 열리고, 추억 스탬프가 하나씩 모입니다.

![백양로](docs/screenshots/02_library_union.jpg)

| | |
|---|---|
| ![언더우드관](docs/screenshots/03_underwood.jpg) | ![노천극장](docs/screenshots/04_amphitheater.jpg) |
| ![가을 + 필름](docs/screenshots/05_autumn_film.jpg) | ![추억 카드](docs/screenshots/06_memory_card.jpg) |

**바로 해 보기: https://yonsei-alumni.github.io/campus-1997/** (GitHub Pages, `main`에 올리면 `.github/workflows/pages.yml`이 다시 배포)

## 실행

```bash
cd web
npm install
npm run dev          # http://localhost:5197
npm run build        # web/dist 정적 사이트 (정적 호스팅 가능)
```

| 키 | 동작 |
|---|---|
| W S / ↑ ↓ | 앞뒤로 걷기 (Shift 뛰기) |
| A D / ← → | 방향 돌기 |
| 마우스 끌기 · 휠 | 카메라 돌리기 · 가까이/멀리 (걸으면 다시 등 뒤로) |
| E | 가까운 랜드마크의 추억 카드 보기 |
| M | 캠퍼스 지도 (장소를 누르면 순간이동) |
| B | 캠퍼스 둘러보기(버드 아이뷰). 제목 화면의 「캠퍼스 둘러보기」로도 들어갑니다 |
| F | 1997 필름 감성 (색감 · 그레인 · 날짜 스탬프) |
| 1 · 2 · 3 | 계절: 4월 벚꽃 / 5월 신록 / 10월 은행잎 |
| Esc | 일시정지 · 옵션 (그림자/AO 품질) |

조작과 카메라는 sim-office와 같은 방식입니다. 내 캐릭터를 3인칭으로 보며 걷고, 카메라가 등 뒤에서 따라옵니다.
제목 화면에서 1997년 학생 여섯 명 가운데 한 명을 고릅니다.
모바일에서는 왼쪽 가상 스틱으로 걷고 돌며(끝까지 밀면 뛰기), 화면을 끌어 카메라를 돌립니다.
캠퍼스 둘러보기는 sim-office의 「마을 둘러보기」처럼 캠퍼스 위를 자유롭게 날아다니는 카메라입니다. 높은 하늘에서부터 눈높이까지 내려갈 수 있습니다.

| 키 | 둘러보기 |
|---|---|
| W S / ↑ ↓ · A D / ← → · Q E | 앞뒤로 날기 · 회전 · 옆으로 |
| Z X / 휠 · R F | 가까이·멀리 · 높이(내려다보는 각도) |
| Shift · Space | 빠르게 · 자동 회전 |
| T · Y · 1 2 3 | 계절 바꾸기 · 1997 필름 · 계절 고르기 |
| 마우스 끌기 · 오른쪽 끌기 · 더블클릭 | 둘러보기 · 밀어서 이동 · 그곳으로 날아가기 |
| 장소 핀 | 그곳으로 날아가 「여기서 걷기」(제목 화면에서 왔으면 바로 시작)·「추억 보기」 |
| Esc / B | 걷기(또는 처음 화면)로 돌아가기 |

아래 막대에는 계절·필름·자동 회전·「거리 높이」(눈높이로 내려가기)·「전체 보기」·높이·확대 버튼이 있습니다. 모바일에서는 한 손가락으로 밀고, 두 손가락으로 확대·회전합니다.

## 무엇이 들어 있나

- **실측 배치**: OpenStreetMap 건물 외곽선과 도로, 그리고 AWS Terrarium 고도 데이터로 만든 지형(안산 · 인왕산 · 북한산 원경 포함). 먼 산에는 숲 덩어리를 깔고, 안산 정상에는 1997년 사진에 보이는 송신탑을 세웠습니다.
  1997년 이후에 지은 건물(학술정보원, 공학원, 새천년관, 경영관, 백양누리 등)은 빼고, 백양로는 2015년 재창조 이전의
  1997년 항공사진(`reference.pdf` 4·5쪽)대로 **중앙분리대 없는 2차선 차도(흰 점선 중앙선 · 노란 가장자리선) + 양쪽 회양목 띠 +
  넓은 보도블록 + 바깥 식재대의 은행나무 가로수와 생울타리** 모습으로 다시 만들었습니다. 정문 안쪽에는 노랑·흰 빗금 과속방지턱과 ◇ 표시가 있습니다.
  정문 안 왼편에는 생울타리와 붉은 철쭉, 소나무, 표지석, 안내판이 있는 화단섬이 있고, 백주년기념관 앞 잔디에는 나무 그늘 주차장이 있습니다.
- **Blender로 직접 모델링한 랜드마크** (`blender/landmarks.py`)
  - 중앙도서관: 아치형 열주 스크린, 커튼월, 아틱 밴드 (밝은 회색 석재 패널)
  - 학생회관: 필로티와 V자 격자 프리캐스트 콘크리트 파사드, 세로 현수막
  - 백주년기념관: 2층 석재 기단 위로 솟은 큰 원통(가로 줄눈), 원통 뒤 무대 탑, 백양로 쪽 깊고 어두운 현관
  - 언더우드관 · 스팀슨관 · 아펜젤러관: 석조 고딕, 총안 탑, 첨두아치 현관, 도머, 담쟁이
  - 대강당, 루스채플, 제1공학관(잡석 마감 측벽), 광혜원(팔작지붕 한옥), 옛 노천극장(잔디 계단식 객석)
  - 독수리상 (`blender/statues.py`): 연세대 공식 자료(높이 12.3m, 청동 독수리 높이 2.6m · 폭 5.2m, 네 면에 「연세인」 부조)대로
    계단식 단 · 부조 기단 · 흰 사각 기둥 위에 날개를 V자로 들어 올린 청동 독수리(첫째날개깃을 손가락처럼 펼침, 바위를 움켜쥔 발톱)
  - 언더우드 동상 (`blender/statues.py`): 언더우드관 앞 정원 입구의 둥근 계단 위, 위가 좁아지는 화강석 받침대(청동 명판)에
    연미복 차림으로 두 팔을 앞으로 벌린 청동상. Quaternius CC0 정장 인물에 자세를 잡고 연미복 자락을 더함
  - 정문(延世大學校 현판)
- **절차적 건물 생성기** (`blender/generic.py`): 나머지 건물 200여 동을 실제 외곽선으로 세우고, 창호(깊이감 있는 창틀 · 문설주 · 창대),
  층 밴드, 파라펫, 옥상 설비, 1990년대 주택가의 녹색 방수 옥상, 물탱크, 상점 간판(독수리다방, 연세문구, 복사·제본 …)을 붙입니다.
- **수목** (`blender/vegetation.py`): 은행나무, 느티나무, 소나무, 벚나무, 단풍나무, 참나무를 가지 골격 + 잎 카드로 생성합니다.
  수관 구형 노멀과 버텍스 AO를 넣었고, 계절별 잎 아틀라스(`tools/make_textures.py`)를 씁니다. 먼 나무는 실행 중에 렌더링한 임포스터로 바꿔 그립니다.
- **사람** (`blender/characters.py`, sim-office의 인물 빌드 방식을 그대로 가져옴): Quaternius의 CC0 *Ultimate Modular Men/Women*에서
  머리·몸·다리·발 부품을 섞고 1997년 옷차림으로 다시 칠했습니다. 흰 티와 청바지, 체크 셔츠, 남색 후드티, 연세 응원단 파란 점퍼,
  갈색 염색 머리, 콤비 재킷, 베이지·남색 롱원피스, 카디건, 교수님, 교직원 등 14명이고 키는 실제 크기(남 1.73m, 여 1.61m)입니다.
  애니메이션(idle, walk, sprint, emote …)은 남녀 리그 파일 두 개에 들어 있고, 걷기·뛰기 속도에 맞춰 재생 속도를 바꿔서 발이 미끄러지지 않습니다.
  학생들은 백양로 보도와 캠퍼스 길을 오가다가 내가 앞을 막으면 멈추고, 광장 곳곳에서는 무리 지어 이야기하며 가끔 고개를 끄덕입니다.
- **자동차** (`blender/cars.py`): 1990년대 국산차 느낌의 중형 세단 두 종, 5도어 소형 해치백, 개인택시, 승합차, 시내버스를 Blender에서 모델링했습니다.
  단면을 몇 cm마다 이어 붙이는 로프트 방식이라 휠하우스, 보닛 선, 모서리가 매끈하게 이어집니다.
  유리·검은 고무 몰딩·필러를 면마다 나눠 칠했고, 크롬 테두리 헤드램프, 그릴, 감싸는 범퍼, 사이드 몰딩, 도어 틈과 손잡이, 사이드미러, 와이퍼, 안테나를 붙였습니다.
  2004년 이전의 두 줄 번호판(자가용 녹색 "서울 33 / 가 1997", 영업용 노란색), 택시 지붕등 "개인", 버스 행선판 "7024 연세대 · 신촌"도 넣었습니다.
  차 안에는 좌석·대시보드·핸들이 있고, 달리는 차에는 Quaternius 인물이 운전석에 앉아 있습니다.
  도장은 클리어코트 재질이고, 바퀴는 달린 거리만큼 굴러가며, 속도를 줄이면 브레이크등이 켜집니다. 사람(나)을 보면 멈추고 앞차와 간격을 둡니다.
- **소품 · 생활감**: 백양로의 양팔 가로등과 광장의 쌍구 가로등, 보도의 흰 세로 깃발, 정문 앞 흰 원형 화분, 배달 오토바이, 공중전화, 벤치,
  1997년 현수막(항공사진에서 읽은 “㉢ 창립 7주년 기념 세미나 및 학부모 초빙 행사 ㉧”, “기술고등고시 설명회”, “… 설계공동연구소 10주년 기념식 및 초청강연회”,
  그리고 “독수리여! 본질을 꿰뚫는 이성으로”, “거친파도 해치고 나가자. 연세!” …), 1997년 사진을 붙인 게시판, 걸어 다니는 학생들.
  나무 줄기와 잎은 카메라 가까이에 오면 디더링으로 비쳐 보여서 3인칭 시야를 가리지 않습니다.
- **렌더링**: three.js PBR, 지형 스플랫 셰이더(잔디/아스팔트/보도블록/흙), HDRI 하늘과 환경광, 4K 그림자, N8AO 앰비언트 오클루전, AgX 톤매핑.

## 에셋 파이프라인 (다시 빌드하기)

```bash
python3 -m venv .venv && .venv/bin/pip install numpy scipy shapely pillow
python3 tools/fetch_polyhaven.py textures 1k <이름…>   # CC0 텍스처/모델/HDRI 내려받기 (assets_src/)
python3 tools/fetch_terrain.py near && python3 tools/fetch_terrain.py far
.venv/bin/python tools/build_campus.py            # OSM + 지형 -> data/campus.json, 지형 bin, 스플랫맵
.venv/bin/python tools/make_textures.py           # 잎 아틀라스, 간판, 정문 현판
.venv/bin/python tools/prepare_web_textures.py    # PBR 텍스처 -> web/public
blender -b --factory-startup --python blender/build.py            # 모든 GLB 빌드
blender -b --factory-startup --python blender/build.py -- blend   # + 편집용 assets_src/yonsei1997_campus.blend
blender -b --factory-startup --python blender/sky_bake.py         # 하늘 텍스처, 태양 방향
blender -b --factory-startup --python blender/characters.py       # 사람 14명 + 리그 2개 (assets_src/quaternius/ 필요)
```

`blender/build.py` 에 `buildings landmarks road veg props polyhaven` 를 인자로 주면 해당 부분만 다시 빌드합니다.
GLB에는 형상, UV, 재질 *이름* 만 들어 있고, 실제 PBR 재질은 `blender/materials.json` 하나를 Blender와 웹이 같이 씁니다.

## 소개 영상

`tools/trailer/`: 게임 화면을 한 프레임씩 렌더링해 46초 소개 영상(1920×1080, 30fps)을 만듭니다.
버드 아이뷰로 캠퍼스 위를 날다가 1997년 항공사진처럼 백양로로 내려가고, 걷는 사람 뒤로 내려앉아 백양로를 걷습니다.

```bash
python3 tools/trailer/frame_server.py /tmp/frames-dir/frames &   # 프레임 받는 로컬 서버 (127.0.0.1:8765)
# npm run dev 로 띄운 게임의 브라우저 콘솔에 tools/trailer/record.js 를 붙여 넣고 끝날 때까지 기다림
python3 tools/trailer/make_video.py /tmp/frames-dir trailer/campus1997_trailer.mp4   # 자막을 넣어 MP4로
```

## 출처 · 라이선스

- 지도 데이터: © OpenStreetMap contributors, ODbL
- 고도: AWS Terrain Tiles (Mapzen Terrarium; SRTM 등)
- 텍스처 · HDRI · 일부 소품(공중전화, 벤치, 휴지통): [Poly Haven](https://polyhaven.com), CC0
- 인물과 애니메이션: Quaternius [Ultimate Modular Men](https://quaternius.com/packs/ultimatemodularmen.html) · [Ultimate Modular Women](https://quaternius.com/packs/ultimatemodularwomen.html), CC0 (빌드 스크립트는 sim-office의 `tools/office-characters.py`를 고쳐 씀)
- 글꼴: Noto Sans KR, Jua, Do Hyeon (SIL OFL)
- 동상 모델링 참고(배포하지 않음): Wikimedia Commons의 언더우드 동상 사진(Rickinasia, CC BY-SA 4.0 등), 연세대 상징물 소개 페이지,
  연세춘추 「'버추얼 캠퍼스', 우리대학교 네 번째 교정 출범」(2024)
- 1997년 사진: `reference.pdf` (연세대학교 기록관 · 연세동문회보 · 연세춘추 · 동문 제공). 동문회 비영리 용도로만 쓰고, 재배포할 때는 원 출처의 허락을 받아야 합니다.

## 고증 메모

건물의 1997년 존재 여부와 층수, 독수리상 위치, 옛 노천극장의 방향, 현수막 문구 일부는 사진과 공개 자료로 추정했습니다.
틀린 곳을 알려 주시면 `tools/build_campus.py` 의 건물 표(`B`)와 `LANDMARKS` 만 고쳐서 다시 빌드하면 됩니다.
