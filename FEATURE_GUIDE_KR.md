# DualSense Haptic Translator 기능 가이드 KR

이 문서는 앱 안의 도움말/설명 팝업으로 옮기기 위한 기능 설명 원본입니다. 각 항목은 짧은 설명을 우선하며, 값이 클수록 강해지는 항목은 특별한 설명이 없는 한 해당 효과가 더 강하거나 더 빨리 반응합니다.

## 1. 앱의 목적

DualSense Haptic Translator는 Forza Horizon의 UDP 텔레메트리를 읽어 DualSense의 햅틱 오디오 채널과 적응형 트리거 출력으로 변환하는 실험적 도구입니다. 게임패드 입력 에뮬레이터가 아니며, Steam Input, DS4Windows, DSX 같은 입력 도구를 대체하지 않습니다.

## 2. 첫 실행 흐름

1. DualSense를 Windows에 연결합니다. USB 연결을 권장합니다.
2. 앱을 실행합니다.
3. `Select DualSense`를 눌러 실제 사용할 DualSense 오디오 재생 장치를 선택합니다.
4. `Test & Save`로 햅틱과 L2/R2 확인 테스트를 실행합니다.
5. Forza Horizon에서 `DATA OUT`을 켜고 IP를 `127.0.0.1`, 포트를 앱의 UDP 포트와 맞춥니다.

## 3. 상단 상태 영역

| 항목 | 설명 |
| --- | --- |
| `UDP` | Forza Horizon Data Out을 받을 포트입니다. 기본값은 `8800`입니다. |
| `DualSense Status` | DualSense 장치 선택, 서버 시작, 테스트 상태를 보여줍니다. |
| `Select DualSense` | DualSense 오디오 장치를 선택하고 테스트하는 팝업을 엽니다. |
| `HUD ALL ON/OFF` | 모든 HUD 창을 한 번에 켜거나 끕니다. |
| `HUD SETTINGS` | 개별 HUD 켜기/끄기, 위치 초기화, 스냅 설정을 여는 메뉴입니다. |
| `Standby Hide` | 주행 데이터가 없거나 대기 상태일 때 HUD를 숨깁니다. |
| `HUD Scale` | HUD 창의 표시 크기를 `100/150/200%`로 바꿉니다. |
| `Main UI Scale` | 메인 앱 UI 크기를 바꿉니다. 적용 후 재시작이 필요할 수 있습니다. |
| `Display Scale` | Windows DPI/디스플레이 배율에 맞춘 보정값입니다. 적용 후 재시작됩니다. |
| `Move Display` | HUD나 앱 창을 다른 모니터 위치로 이동합니다. |
| `Preset` | 햅틱/트리거 프리셋을 선택합니다. 현재 선택된 프리셋은 노란색으로 표시됩니다. |
| `SAVE` | 현재 프리셋과 공용 설정을 저장합니다. 저장할 변경이 있을 때 노란색으로 표시됩니다. |
| `Options` | 백업, HUD 단위, 텔레메트리 릴레이, DSX 출력, 오디오 출력, 표시 옵션 등을 여는 설정 창입니다. |
| `EQ Boost Gain` | Haptic Effects 제목 오른쪽의 버튼으로, `Haptic Low Boost Gain` 팝업을 엽니다. DualSense 오디오 채널로 보내기 직전의 약한 햅틱 파형을 증폭합니다. 기본값은 `0`이며, 먼저 낮은 값부터 테스트하는 것이 좋습니다. |
| `Log Rec` | 텔레메트리와 분석 값을 CSV 로그로 기록합니다. |

## 4. Select DualSense 팝업

| 항목 | 설명 |
| --- | --- |
| 장치 목록 | Windows 재생 장치 중 DualSense 햅틱 출력 후보를 보여줍니다. |
| `Refresh` | 장치 목록을 다시 검색합니다. |
| `Test & Save` | 선택한 장치를 저장하고 서버를 재시작한 뒤 80Hz 햅틱과 L2/R2 테스트를 보냅니다. |
| `Use Selected` / `Save Device` | 선택한 장치를 저장합니다. 테스트 출력이 필요하면 `Test & Save`를 사용합니다. |
| `Cancel` | 변경 없이 창을 닫습니다. |

## 5. 프리셋과 저장

| 항목 | 설명 |
| --- | --- |
| `Base` | 기준 프리셋입니다. 기본적인 균형값을 담습니다. |
| `Soft` | 피로도를 낮춘 약한 출력 프리셋입니다. |
| `Semi-Strong` | Soft와 Strong 사이의 중간 강도 프리셋입니다. |
| `Strong` | 더 강한 햅틱과 트리거 감각을 위한 프리셋입니다. |
| `User 1`, `User 2` | 사용자가 자유롭게 조정할 수 있는 개인 프리셋입니다. |
| `Copy preset` | 현재 프리셋에 다른 프리셋 값을 복사합니다. |
| `SAVE` | 현재 선택된 프리셋에 햅틱/트리거 설정을 저장하고, 공용 UI 설정도 저장합니다. |

프리셋은 `effects`와 `trigger_effects`를 저장합니다. 창 위치, HUD 위치, 장치 선택, 스케일 같은 항목은 공용 설정입니다.

## 6. HUD 기능

| HUD | 설명 |
| --- | --- |
| `Pedal` | 액셀/브레이크 입력을 표시합니다. |
| `G-Force` | 차량의 가속/횡가속 방향을 표시합니다. |
| `Tire` | 타이어 슬립/그립 상태를 표시합니다. |
| `Steer` | 차량의 오버스티어와 언더스티어 상태를 이미지화합니다. 오버스티어는 위로, 언더스티어는 아래로 표시되며, 그래프가 넓적하면 그립이 높고 가운데가 뾰족할수록 그립이 약한 상태를 뜻합니다. |
| `RPM` | 엔진 RPM, 속도, 기어 정보를 표시합니다. 속도 표기는 HUD 단위 설정의 `km/h` 또는 `mph`를 따릅니다. |
| `Engine` | 동력과 부스트/진공을 원형 게이지로 표시합니다. 동력은 `hp/PS/kW`, 부스트는 `psi/bar` 단위 설정을 따릅니다. |
| `Haptic` | 앱이 서버로 보내는 햅틱 출력 의도를 L/R 주파수 바 형태로 표시합니다. |
| `Debug Haptic` | 각 햅틱 이펙트의 현재 출력 강도를 게이지로 표시합니다. |
| `Trigger` | L2/R2 입력과 트리거 저항/진동 출력을 표시합니다. |
| `Debug Trigger` | 각 트리거 이펙트를 3줄 게이지로 표시합니다. 양쪽 트리거에 걸리는 이펙트는 L2/R2 줄을 따로 보여줍니다. 노란색은 최근 전체 출력 강도, 파란색은 저항 출력, 마젠타는 Wall 구간, 청록색 세로선은 펄스 방출 위치를 뜻합니다. 위치를 표시하는 줄에서는 왼쪽일수록 트리거를 깊게 당긴 구간입니다. |
| `Drift` | 드리프트 판단 점수와 구성 요소를 표시합니다. |

HUD는 드래그로 이동할 수 있습니다. `HUD Location Reset`은 현재 스케일의 기본 위치와 크기로 되돌립니다. `Snap HUD`는 HUD 이동 시 일정 픽셀 단위로 붙게 합니다.

## 7. 그래프와 로그

| 항목 | 설명 |
| --- | --- |
| Telemetry Graph | RPM, 속도, 입력, 슬립 등 주요 텔레메트리 변화를 보여줍니다. |
| Output Gauge Graph | 현재 선택된 햅틱/트리거 효과의 출력 강도를 보여줍니다. |
| Telemetry Field | 표시할 텔레메트리 필드를 선택하거나 숨깁니다. |
| `Log Rec` | 주행 중 텔레메트리와 이벤트 판단 값을 CSV로 저장합니다. |

## 8. Options 창

| 항목 | 설명 |
| --- | --- |
| `Load Backup` | 이전 설정 백업을 불러옵니다. |
| `Language` | Main UI와 Tooltip의 차후 언어 대상을 따로 선택합니다. 현재는 선택 구조만 있으며 실제 문구 번역 적용은 아직 연결하지 않았습니다. |
| `HUD Units` | HUD 표시 단위를 선택합니다. Speed는 RPM HUD 속도 표기, Power는 Engine HUD 상단 동력 게이지, Boost는 Engine HUD 부스트/진공 게이지에 적용됩니다. 햅틱 로직, 트리거 로직, 로그 값은 바꾸지 않습니다. |
| `DSX Trigger UDP Bridge` | DSX가 받을 수 있는 UDP 트리거 명령을 함께 보냅니다. |
| `Audio Export Mode` | DSX/오디오 출력 관련 실험적 내보내기 옵션입니다. |
| `Audio Output Device` | DSX 오디오 내보내기에 사용할 출력 장치입니다. DualSense 햅틱 장치 선택과는 별도입니다. |
| `Haptic Audio Volume` | 서버에 보내는 햅틱 오디오 마스터 볼륨입니다. |
| `Apply` | 마스터 볼륨이나 오디오 관련 변경을 서버에 적용합니다. |
| `HUD Location Reset` | 모든 HUD 위치/크기를 기본값으로 되돌립니다. |
| `Display Scale` | Windows 표시 배율에 맞춰 앱 전체 표시를 보정합니다. |

## 9. 햅틱 이펙트 공통 항목

| 항목 | 설명 |
| --- | --- |
| `ON` | 해당 햅틱 효과를 켜거나 끕니다. |
| `Volume` | 해당 효과의 출력 크기입니다. |
| `L/R Balance` | 좌우 햅틱 채널의 배치입니다. `5`는 양쪽, 낮으면 왼쪽, 높으면 오른쪽 중심입니다. |
| `Setting` 패널 | 선택한 효과의 세부 튜닝 항목을 보여줍니다. |

## 10. 햅틱 이펙트 설명

### Gear Shift Bite - Core
기어 변속의 중심 충격입니다. 변속 순간의 짧고 확실한 물림감을 담당합니다.

- `Up/Down Balance`: 업시프트/다운시프트의 좌우 배치 비율입니다.
- `Punch`: 첫 타격의 강도입니다.
- `Length`: 변속 충격의 전체 길이입니다.
- `Tail`: 충격 뒤에 남는 잔향입니다.
- `Tone`: 변속 감각의 음색/주파수 느낌입니다.
- `L/R Balance`: 효과의 좌우 출력 배치입니다.

### Gear Shift Bite - High Hz
Core 뒤에 붙는 높은 주파수의 빠른 질감입니다. 금속성, 날카로움, 빠른 변속감을 보강합니다.

- `Up/Down Balance`, `Punch`, `Length`, `Tail`, `Tone`, `L/R Balance`: Core와 같은 의미입니다.

### Gear Shift Bite - Particles
변속 뒤에 흩어지는 작은 입자감입니다. 충격을 한 번으로 끝내지 않고 여러 작은 떨림으로 분산합니다.

- `Up/Down Balance`, `Punch`, `Length`, `Tail`, `Tone`, `L/R Balance`: Core와 같은 의미입니다.

### Rev limit
엔진 RPM이 레드존 근처에 접근할 때 지속적인 떨림을 만듭니다.

- `L/R Balance`: 좌우 출력 배치입니다.
- `RPM Position`: Rev limit 효과가 시작되는 RPM 위치입니다.
- `Fade Range`: 시작 이후 최대 출력까지 올라가는 구간입니다.
- `Tone`: 출력의 음색입니다.
- `Pulse Rate`: 끊기는 느낌 또는 맥동 속도입니다.
- `Punch`: 레브 리미트 진입 시 타격감입니다.
- `Vehicle RPM Scaling`: 차량별 RPM 특성 반영 정도입니다.
- `Max Gear Limit`: 최고단에서 지속 피로감을 줄이는 정도입니다.
- `Downshift Surge`: 다운시프트 직후 RPM 상승 타격입니다.
- `Climb Strength`: RPM이 리미터로 올라갈 때의 상승감입니다.

### Rumble Kerbs
연석이나 럼블 스트립을 밟을 때의 반복적인 노면 질감입니다. 좌우 출력은 앞바퀴 접촉에 따라 결정됩니다.

- `Speed Low Start km/h`: 저속 기준 속도입니다.
- `Speed High Max km/h`: 고속 기준 속도입니다.
- `Low Speed Hz`: 저속에서 사용할 주파수입니다.
- `High Speed Hz`: 고속에서 사용할 주파수입니다.
- `Bump Sharpness`: 연석 돌기의 날카로움입니다.

### Tire Limit Load
타이어가 한계 그립에 가까워지는 느낌입니다. 완전한 미끄러짐보다 직전의 문지름/하중 변화를 표현합니다.

- `Entry Threshold`: 효과가 시작되는 한계 접근 지점입니다.
- `Full Load Point`: 최대 출력에 도달하는 지점입니다.
- `Low Load Hz`: 낮은 하중에서의 주파수입니다.
- `High Load Hz`: 높은 하중에서의 주파수입니다.
- `Attack`: 효과가 올라오는 속도입니다.

### Wheelspin Buzz
강한 스로틀 출력으로 구동축 타이어가 더 빠르게 스핀하여 파워슬라이드를 일으키는 상태일 때 햅틱 진동을 방출합니다.

- `L/R Balance`: 좌우 출력 배치입니다.
- `Slip Start Offset`: 휠스핀 시작점을 앞당기거나 늦춥니다.
- `Buzz Hz`: 버즈의 중심 주파수입니다.
- `Noise Range`: 주파수에 약간의 흔들림을 추가하는 범위입니다.
- `Attack`: 버즈가 올라오는 속도입니다.

### Road Bumps
도로 요철, 작은 충격, 서스펜션 움직임을 표현합니다.

- `Bump Sensitivity`: 작은 요철을 감지하는 민감도입니다.
- `Low Class Correction`: 저성능/저속 차량의 요철 보정 정도입니다.
- `Small Bump Strength`: 작은 요철 출력 강도입니다.
- `Large Bump Strength`: 큰 요철 출력 강도입니다.
- `Low Bump Hz`: 큰 요철 쪽 주파수입니다.
- `High Bump Hz`: 작은 요철 쪽 주파수입니다.
- `Attack`: 요철 출력이 올라오는 속도입니다.
- `Decay`: 요철 출력이 사라지는 속도입니다.

### Impacts
벽이나 차량과의 전방/일반 충돌을 표현합니다.

- `Speed Drop Threshold`: 충돌로 판단할 속도 감소 기준입니다.
- `G Force Threshold`: 충돌로 판단할 G-force 기준입니다.
- `Slip Influence`: 타이어 슬립이 충돌 강도 계산에 반영되는 정도입니다.
- `Impact Punch`: 첫 충격의 강도입니다.
- `Impact Length`: 충격 지속 시간입니다.
- `Low Impact Hz`: 강한 충돌 쪽 주파수입니다.
- `High Impact Hz`: 약한 충돌 쪽 주파수입니다.

### Impact - Side
측면 접촉, 차체 옆면 충돌, 가벼운 스침을 표현합니다.

- `Side Sensitivity`: 측면 충돌 감지 민감도입니다.
- `Bump Rejection`: 요철을 측면 충돌로 오인하지 않도록 거르는 강도입니다.
- `Scrape Strength`: 긁히는 느낌의 강도입니다.
- `Side Length`: 측면 충돌 출력 길이입니다.

### Impact - Smashable
표지판, 울타리, 작은 오브젝트 등 파괴 가능한 물체와의 빠른 충돌을 표현합니다.

- `Smash Sensitivity`: 작은 오브젝트 충돌 감지 민감도입니다.
- `Repeat Cooldown`: 반복 충돌 사이 최소 간격입니다.
- `Smash Punch`: 첫 짧은 타격 강도입니다.
- `Rattle Strength`: 부서지는 잔떨림 강도입니다.
- `Smash Length`: 전체 출력 길이입니다.
- `Light Object Hz`: 가벼운 물체 충돌 주파수입니다.
- `Heavy Object Hz`: 무거운 물체 충돌 주파수입니다.

## 11. 트리거 이펙트 공통 항목

| 항목 | 설명 |
| --- | --- |
| `ON` | 해당 트리거 효과를 켜거나 끕니다. |
| `Curve` | 입력 대비 저항 변화 곡선입니다. |
| `Resistance Strength` | 트리거 저항의 강도입니다. |
| `Resistance Start Position` | 저항이 시작되는 트리거 위치입니다. |
| `Resistance Max Position` | 저항이 최대가 되는 위치 또는 벽 위치입니다. |
| `Smooth Start` | 저항이 갑자기 튀지 않도록 올라오는 시간입니다. |
| `Side`, `L/R` | 효과를 L2, R2 또는 양쪽에 보낼지 정합니다. |

## 12. 트리거 이펙트 설명

### Drift Rumble Fade
드리프트 주행 중 특정 햅틱/트리거 출력을 줄이는 중앙 페이드 레이어입니다.

- `Condition Strictness`: 값이 높을수록 Fade에 쉽게 진입하고, 낮을수록 엄격해집니다.
- `Wheelspin Buzz`: Fade 중 남길 Wheelspin 햅틱 출력량입니다.
- `Throttle Pressure`: Fade 중 남길 R2 스로틀 압력 저항입니다.
- `Throttle Traction`: Fade 중 남길 R2 트랙션 저항/진동입니다.
- `Acceleration G Punch`: Fade 중 남길 가속 펀치 출력입니다.
- `RPM Rev Limit`: Fade 중 남길 RPM 리미트 트리거 출력입니다.

### Brake Pressure
브레이크 입력량에 따라 L2 저항을 만듭니다.

- `Resistance Strength`: 브레이크 저항 강도입니다.
- `Resistance Start Position`: 저항 시작 위치입니다.
- `Resistance Max Position`: 최대 저항 위치입니다.

### Brake Resistance
브레이크 페달에 기본 벽/저항감을 만듭니다.

- `Curve`: 저항 증가 곡선입니다.
- `Resistance Start Position`: 저항 시작 위치입니다.
- `Resistance Max Position`: 최대 저항 위치입니다.
- `Resistance Strength`: 저항 강도입니다.
- `Smooth Start`: 저항 상승 시간입니다.
- `Slip Threshold`: 슬립 기반 반응 기준입니다.
- `Slip Response Mode`: 슬립 발생 시 저항 반응 방식입니다.

### Brake Resistance - Predictive
브레이크 입력과 타이어 상태를 보고 잠김/슬립을 예측해 L2 저항을 조정합니다.

- `Base Wall Position`: 기본 벽 위치입니다.
- `Minimum Wall Position`: 예측 반응 시 벽이 이동할 수 있는 최소 위치입니다.
- `Prediction Strength`: 예측 반응 강도입니다.
- `Slip Off Threshold`: 슬립이 커졌을 때 저항을 줄이는 기준입니다.
- `Slip Drop Low Resistance`: 슬립 시 남길 최소 저항입니다.
- `Slip Pulse Start/End Level`: 슬립 펄스가 발생하는 출력 범위입니다.
- `Strong Pulse Amplitude/Rate`: Strong Pulse 방식의 슬립 펄스 강도와 속도입니다.
- `Soft Pulse Amplitude/Frequency/Start Zone`: Soft Pulse 방식의 진동 강도, 주파수, 시작 위치입니다.

### Throttle Pressure
가속 입력량에 따라 R2 저항을 만듭니다.

- `Resistance Strength`: 스로틀 저항 강도입니다.
- `Resistance Start Position`: 저항 시작 위치입니다.
- `Resistance Max Position`: 최대 저항 위치입니다.
- `Smooth Start`: 저항 상승 시간입니다.

### Throttle Resistance - Traction
가속 중 구동휠 슬립에 따라 R2 저항과 펄스를 조정합니다.

- `Resistance Strength`: 기본 저항 강도입니다.
- `Minimum Wall Position`: 슬립 반응 시 벽 위치입니다.
- `Prediction Strength`: 슬립 예측 강도입니다.
- `Slip Threshold`: 슬립 반응 시작 기준입니다.
- `Slip Off End`: 슬립 반응이 끝나는 기준입니다.
- `Slip Off Resistance`: 슬립 시 남길 저항입니다.
- `Slip Pulse Start/End Level`: 슬립 펄스 출력 범위입니다.
- `Slip Pulse Strong/Soft Pulse`: 슬립 펄스의 Strong Pulse 또는 Soft Pulse 출력 세부값입니다.

### Gear Shift Kick
변속 순간 L2/R2 트리거에 짧은 킥을 줍니다.

- `Upshift Kick Strength`: 업시프트 킥 강도입니다.
- `Upshift Kick Duration`: 업시프트 킥 길이입니다.
- `Upshift Side`: 업시프트 킥을 보낼 트리거입니다.
- `Downshift Kick Strength`: 다운시프트 킥 강도입니다.
- `Downshift Kick Duration`: 다운시프트 킥 길이입니다.
- `Downshift Side`: 다운시프트 킥을 보낼 트리거입니다.
- `Early Input Soft Zone`: 입력 초반을 부드럽게 처리하는 구간입니다.
- `Kick Late Position`: 킥이 늦게 걸리는 위치입니다.
- `Kick Softness`: 킥의 날카로움/부드러움입니다.
- `Kick Release Duration`: 킥 해제 시간입니다.

### Collision Kick
충돌 시 트리거에 짧은 충격을 줍니다.

- `Kick Strength`: 충돌 킥 강도입니다.
- `Kick Duration`: 충돌 킥 길이입니다.

### Kerb Soft Pulse
연석 접촉 시 L2/R2 트리거에 Soft Pulse 계열 피드백을 줍니다.

- `L2 Trigger Start Position`: L2 Soft Pulse 시작 위치입니다.
- `L2 Speed Frequency Range`: 속도에 따른 L2 주파수 범위입니다.
- `L2 Speed Soft Pulse Amplitude Range`: 속도에 따른 L2 Soft Pulse 강도 범위입니다.
- `R2 Trigger Start Position`: R2 Soft Pulse 시작 위치입니다.
- `R2 Speed Frequency Range`: 속도에 따른 R2 주파수 범위입니다.
- `R2 Speed Soft Pulse Amplitude Range`: 속도에 따른 R2 Soft Pulse 강도 범위입니다.

### RPM Rev Limit
RPM이 리미터 근처에 있을 때 트리거 펄스/진동을 만듭니다.

- `Trigger Style`: RPM 트리거 출력 방식입니다.
- `Pulse Start Position`: 펄스가 시작되는 RPM 위치입니다.
- `Strong Pulse Amplitude`: Strong Pulse 방식 강도입니다.
- `Strong Pulse Rate`: Strong Pulse 반복 속도입니다.
- `Soft Pulse Amplitude`: Soft Pulse 방식 강도입니다.
- `Soft Pulse Frequency`: Soft Pulse 방식 주파수입니다.
- `Soft Pulse Start Zone`: Soft Pulse가 시작되는 트리거 영역입니다.

### Impact Tick
작은 충돌이나 충격을 짧은 tick으로 표현합니다.

- `Tick Amplitude`: tick 강도입니다.
- `Tick Frequency`: tick 주파수입니다.
- `Tick Start Zone`: tick 시작 위치입니다.
- `Tick Duration`: tick 길이입니다.

### 숨겨진 개발용 항목
`Brake Resistance - Dynamic`과 `Trigger Mode Test`는 일반 UI에서 숨겨진 개발/실험용 항목입니다. 코드에는 남아 있지만 릴리즈 사용자가 직접 조정하는 항목은 아닙니다.

## 13. DSX / DS4Windows 관련

- DSX UDP Bridge는 DSX를 사용하는 환경에서 트리거 명령을 추가로 보내기 위한 실험적 기능입니다.
- DS4Windows는 Xbox App / Windows Store 버전에서 DualSense를 Xbox 360 컨트롤러처럼 인식시키는 보조 수단으로 사용할 수 있습니다.
- 이 앱의 햅틱/트리거 출력과 DSX/DS4Windows가 같은 장치를 동시에 제어하면 환경에 따라 충돌할 수 있습니다.

## 14. 설정 저장 위치와 릴리즈 주의

- 릴리즈 빌드는 사용자 PC의 로컬 설정 영역에 설정을 저장합니다.
- `haptic_audio_device`는 사용자 PC마다 다르므로 배포 설정에 포함하지 않습니다.
- `telemetry_grapher_release_settings.json`은 로컬 위치, HUD 배치, 개인 장치명, 로그 상태를 제외한 기본 공용 설정입니다.
