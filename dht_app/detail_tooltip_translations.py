from __future__ import annotations


# Complete, key-based inline descriptions for every active Haptic and Trigger detail.
# Legacy wording is retained where semantics still match; current-only and ambiguous
# duplicate-label settings are translated explicitly.
DETAIL_TOOLTIP_TRANSLATIONS: dict[str, dict[str, str]] = {'KR': {'accel_g_punch': 'Drift Rumble Fade 중 유지할 가속 펀치 레벨입니다.\n높은 값은 페이드 중에도 가속 펀치를 더 유지합니다. 낮은 값은 펀치를 더 적극적으로 줄입니다.',
        'attack': '이펙트가 올라오는 속도입니다.\n낮은 값은 부드럽게 들어옵니다. 높은 값은 더 빠르고 즉각적으로 반응합니다.',
        'balance': '업시프트와 다운시프트의 느낌 균형을 조정합니다.\n낮은 값은 다운시프트 쪽을, 높은 값은 업시프트 쪽을 더 강조합니다.',
        'bump_rejection': '노면 요철을 측면 충돌 감지에서 걸러내는 정도입니다.\n낮은 값은 더 많은 긁힘 반응을 허용합니다. 높은 값은 요철 노이즈를 더 강하게 배제합니다.',
        'bump_sensitivity': '작은 요철에 대한 민감도입니다.\n낮은 값은 작은 표면 변화를 무시합니다. 높은 값은 더 미세한 요철에도 반응합니다.',
        'bump_sharpness': '각 연석 요철의 선명도입니다.\n낮은 값은 질감을 부드럽게 합니다. 높은 값은 개별 홈을 더 뚜렷하게 합니다.',
        'buzz_hz': '주 휠스핀 버즈 주파수입니다.\n낮은 값은 거칠고 무겁게, 높은 값은 더 미세하고 전기적으로 느껴집니다.',
        'climb_strength': 'RPM이 리미터로 올라갈 때의 빌드업입니다.\n낮은 값은 더 평평합니다. 높은 값은 리미터 접근을 더 점진적으로 만듭니다.',
        'condition_strictness': 'Drift Rumble Fade 진입 민감도입니다.\n낮은 값은 더 명확하게 지속되는 드리프트를 요구합니다. 높은 값은 더 쉽게 페이드에 들어갑니다.',
        'curve': '트리거 입력에서 저항으로 이어지는 반응 곡선입니다.\n낮은 값은 더 직접적이고 선형입니다. 높은 값은 힘의 램프를 더 강하게 변형합니다.',
        'decay': '이펙트가 사라지는 속도입니다.\n낮은 값은 더 오래 남습니다. 높은 값은 더 빨리 멈춥니다.',
        'downshift_duration_ms': '다운시프트 킥 지속 시간입니다.\n낮은 값은 빠릅니다. 높은 값은 더 오래 지속됩니다.',
        'downshift_strength_percent': '다운시프트 킥 강도입니다.\n낮은 값은 부드럽습니다. 높은 값은 다운시프트를 더 강하게 칩니다.',
        'downshift_surge': '다운시프트 RPM 점프 이후의 추가 반응입니다.\n낮은 값은 서지를 줄입니다. 높은 값은 다운시프트 회전 상승을 더 뚜렷하게 합니다.',
        'early_input_soft_zone': '초기 트리거 입력 구간을 부드럽게 합니다.\n낮은 값은 킥을 즉각적으로 유지합니다. 높은 값은 킥 전 부드러운 이동 구간을 더 남깁니다.',
        'end_hz': '가속 펀치 끝부분의 햅틱 주파수입니다.',
        'entry_threshold': '그립 한계 이펙트가 시작되는 지점입니다.\n낮은 값은 더 일찍 반응합니다. 높은 값은 타이어가 한계에 더 가까워질 때까지 기다립니다.',
        'fade_range': '시작 지점부터 최대 출력까지의 RPM 범위입니다.\n낮은 값은 빠르게 올라갑니다. 높은 값은 더 점진적으로 쌓입니다.',
        'force_percent': '트리거 저항 강도입니다.\n낮은 값은 누르기 쉽습니다. 높은 값은 더 강한 저항벽을 만듭니다.',
        'full_load_point': '이펙트가 최대 출력에 도달하는 지점입니다.\n낮은 값은 더 빨리 최대 강도에 도달합니다. 높은 값은 더 큰 타이어 하중이 필요합니다.',
        'g_force_threshold': '충돌 감지에 쓰는 G-force 기준입니다.\n낮은 값은 가벼운 충격도 감지합니다. 높은 값은 더 강한 충격을 요구합니다.',
        'gear_drop_offset': '상위 기어 출력 감소 폭입니다. 9는 2/3/4단을 90/80/70으로, 8은 대략 88/75/60으로 만듭니다.',
        'haptic_gear_1_percent': '1단 및 출발 시 햅틱 출력 배율입니다.\n첫 업시프트 전 출발 가속을 강하게 느끼려면 높은 값을 유지합니다.',
        'haptic_gear_2_percent': '2단의 햅틱 출력 배율입니다.\n출발에서 2단까지 이어지는 가속감을 유지하려면 높은 값을 사용합니다.',
        'haptic_gear_3_percent': '3단의 햅틱 출력 기준 배율입니다.\n4단 이상의 출력은 이 값을 기준으로 점차 감소합니다.',
        'haptic_strength': '가속 펀치 레이어의 추가 햅틱 게인입니다.\n낮은 값은 미묘하게 유지합니다. 높은 값은 출발/업시프트 가속감을 더 분명하게 합니다.',
        'heavy_object_hz': '무거운 오브젝트의 주파수입니다.\n낮은 값은 더 무겁고 깊게, 높은 값은 더 날카롭게 느껴집니다.',
        'high_bump_hz': '작거나 가벼운 요철의 주파수입니다.\n낮은 값은 더 부드럽게, 높은 값은 더 날카롭게 느껴집니다.',
        'high_impact_hz': '가벼운 충돌의 주파수입니다.\n낮은 값은 작은 충돌을 부드럽게 합니다. 높은 값은 더 선명하게 만듭니다.',
        'high_load_hz': '높은 타이어 하중의 주파수입니다.\n낮은 값은 하중이 걸린 타이어를 깊게, 높은 값은 한계 근처를 더 날카롭게 만듭니다.',
        'high_speed_hz': '차량이 높은 속도로 연석을 통과할 때 더 빠르게 진동합니다.\n설정한 Hz 값은 최고 속도에서의 진동 빠르기입니다.',
        'howl_amp': 'Shift Down Howl의 Soft Pulse 진폭입니다.\n낮은 값은 은은하며, 높은 값은 Howl을 더 분명하게 느끼게 합니다.',
        'howl_duration_ms': 'Shift Down Howl 펄스의 지속 시간입니다.\n낮은 값은 짧고 단단하며, 높은 값은 다운시프트 울림을 더 오래 유지합니다.',
        'howl_end_hz': 'Shift Down Howl이 끝날 때의 주파수입니다.\n낮은 값은 더 깊게, 높은 값은 더 날카롭게 끝납니다.',
        'howl_noise_percent': 'Howl이 사라지는 동안 주파수와 강도에 섞이는 노이즈입니다.\n낮은 값은 깨끗하며, 높은 값은 더 거칠고 불규칙하게 느껴집니다.',
        'howl_start_hz': 'Shift Down Howl이 시작될 때의 주파수입니다.\n낮은 값은 더 깊게, 높은 값은 더 날카롭게 시작합니다.',
        'howl_start_zone': 'Shift Down Howl의 Soft Pulse 시작 위치입니다.\n낮은 값은 더 일찍 시작하며, 높은 값은 트리거의 더 깊은 위치에서 시작합니다.',
        'impact_length': '충돌 지속 시간입니다.\n낮은 값은 빠릅니다. 높은 값은 충돌을 더 오래 유지합니다.',
        'impact_punch': '첫 충돌 타격 강도입니다.\n낮은 값은 타격을 부드럽게 합니다. 높은 값은 더 갑작스럽게 만듭니다.',
        'kerb_high_hz': '차량이 높은 속도로 연석을 통과할 때 더 빠르게 진동합니다.\n설정한 Hz 값은 최고 속도에서의 진동 빠르기입니다.',
        'kerb_l_enabled': 'Kerb Wave의 L2 출력을 켜거나 끕니다.\nL2를 꺼도 공용 설정과 R2 출력은 유지됩니다.',
        'kerb_l_high_amp': '차량이 높은 속도일 때 L2와 R2에 동일하게 적용되는 Soft Pulse 진폭입니다.\n값을 낮추면 부드러워지고, 높이면 강해집니다.',
        'kerb_l_low_amp': '차량이 낮은 속도일 때 L2와 R2에 동일하게 적용되는 Soft Pulse 진폭입니다.\n값을 낮추면 부드러워지고, 높이면 강해집니다.',
        'kerb_l_start_percent': 'L2와 R2에 동일하게 적용되는 Soft Pulse 시작 위치입니다.\n값을 낮추면 더 일찍 시작하고, 높이면 트리거의 더 깊은 위치에서 시작합니다.',
        'kerb_low_hz': '차량이 낮은 속도일 때 진동의 빠르기입니다.\n차량 속도가 낮을 때는 연석 진동이 빠르지 않도록 설정합니다.',
        'kerb_r_enabled': 'Kerb Wave의 R2 출력을 켜거나 끕니다.\nR2를 꺼도 공용 설정과 L2 출력은 유지됩니다.',
        'kick_late_position': '킥이 더 늦게 도착하는 위치입니다.\n낮은 값은 킥을 앞당깁니다. 높은 값은 트리거 깊은 쪽으로 밀어냅니다.',
        'kick_softness': '킥의 날카로움 또는 부드러움입니다.\n낮은 값은 더 날카롭게, 높은 값은 더 완충된 느낌으로 만듭니다.',
        'kick_strong_pulse_duration_ms': 'Howl 전에 출력되는 짧은 Kick Soft Pulse의 지속 시간입니다.\n낮은 값은 짧고 단단하며, 높은 값은 킥을 더 오래 유지합니다.',
        'kick_strong_pulse_hz': 'Howl 전에 출력되는 짧은 Kick Soft Pulse의 주파수입니다.\n낮은 값은 더 깊게, 높은 값은 더 날카롭게 느껴집니다.',
        'kick_strong_pulse_strength': 'Howl 전에 출력되는 짧은 Kick Soft Pulse의 강도입니다.\n낮은 값은 부드럽고, 높은 값은 다운시프트 체결감을 더 분명하게 합니다.',
        'large_bump_strength': '큰 요철의 출력 게인입니다.\n낮은 값은 큰 충격을 부드럽게 합니다. 높은 값은 무거운 요철을 더 강하게 만듭니다.',
        'launch_wall_fade_percent': '출발 저항이 RPM 구간에서 이 지점까지 최대 강도를 유지한 뒤 페이드됩니다.',
        'length': '타격의 전체 지속 시간입니다.\n낮은 값은 짧고 타이트합니다. 높은 값은 더 길고 지속됩니다.',
        'light_object_hz': '가벼운 오브젝트의 주파수입니다.\n낮은 값은 부드럽게, 높은 값은 선명하게 만듭니다.',
        'low_bump_hz': '크거나 무거운 요철의 주파수입니다.\n낮은 값은 더 깊게, 높은 값은 더 타이트하게 느껴집니다.',
        'low_class_correction': '느리거나 낮은 클래스 차량을 위한 보정입니다.\n낮은 값은 원본 출력에 가깝습니다. 높은 값은 저속 차량도 더 쉽게 느껴지게 합니다.',
        'low_impact_hz': '강한 충돌의 주파수입니다.\n낮은 값은 깊고 무겁게, 높은 값은 날카롭게 느껴집니다.',
        'low_load_hz': '낮은 타이어 하중의 주파수입니다.\n낮은 값은 더 무겁게, 높은 값은 진입부를 더 밝게 느끼게 합니다.',
        'low_speed_hz': '차량이 낮은 속도일 때 진동의 빠르기입니다.\n차량 속도가 낮을 때는 연석 진동이 빠르지 않도록 설정합니다.',
        'max_gear_limit': '최고단에서 피로감을 줄이는 값입니다.\n낮은 값은 고단에서도 리미터 진동을 더 유지합니다. 높은 값은 지속적인 최고단 버즈를 더 줄입니다.',
        'max_percent': '저항이 최대에 도달하는 위치입니다.\n낮은 값은 더 이른 저항벽을 만듭니다. 높은 값은 벽을 트리거 깊은 쪽으로 옮깁니다.',
        'max_rpm_offset': '출력 구간 오프셋입니다. 10은 1단 100% max RPM, 2단 90%를 의미합니다.',
        'noise_range': '버즈 주파수 주변의 변동 범위입니다.\n낮은 값은 안정적입니다. 높은 값은 더 많은 랜덤 질감을 추가합니다.',
        'pan': '출력을 좌/우 햅틱 채널에 배치합니다.\n5는 중앙입니다. 낮은 값은 왼쪽, 높은 값은 오른쪽을 더 강조합니다.',
        'pulse_gear_1_percent': '1단과 출발에서 Soft/Strong Pulse 펄스 출력 스케일입니다.',
        'pulse_gear_2_percent': '2단의 Soft/Strong Pulse 펄스 출력 스케일입니다. 런치와 2단을 연속적으로 느끼려면 높게 유지합니다.',
        'pulse_gear_3_percent': '3단의 Soft/Strong Pulse 기준 출력 스케일입니다. 더 높은 기어는 이 값에서 점차 감쇠됩니다.',
        'pulse_rate': '펄스 또는 채터링 속도입니다.\n낮은 값은 느리고 무겁게, 높은 값은 빠르고 예민하게 느껴집니다.',
        'pulse_start_percent': '펄스가 시작되는 위치입니다.\n낮은 값은 더 일찍 시작합니다. 높은 값은 구간의 뒤쪽까지 지연합니다.',
        'pulse_strength': '트리거 펄스 반응 강도입니다.\n낮은 값은 미묘합니다. 높은 값은 펄스를 더 쉽게 느끼게 합니다.',
        'punch': '첫 타격의 강도입니다.\n낮은 값은 충격을 부드럽게 합니다. 높은 값은 첫 물림감을 더 단단하게 만듭니다.',
        'rattle_strength': '파편과 잔진동의 강도입니다.\n낮은 값은 후속 떨림을 줄입니다. 높은 값은 깨지는 물체 질감을 더합니다.',
        'release_duration_ms': '킥 이후 해제 시간입니다.\n낮은 값은 빠르게 풀립니다. 높은 값은 킥이 서서히 사라집니다.',
        'repeat_cooldown': '반복되는 파괴 오브젝트 충돌 사이의 최소 시간입니다.\n낮은 값은 빠른 반복 틱을 허용합니다. 높은 값은 과밀한 반복 출력을 막습니다.',
        'rpm_position': '이펙트가 시작되는 RPM 지점입니다.\n낮은 값은 더 일찍 시작하며, 높은 값은 레드라인에 가까워질 때까지 출력을 늦춥니다.',
        'rpm_rev_limit': 'Drift Rumble Fade 중 유지할 RPM Rev Limit 트리거 레벨입니다.\n낮은 값은 리미트 트리거 출력을 더 줄입니다. 높은 값은 더 많이 유지합니다.',
        'scrape_strength': '긁힘/차체 접촉 부분의 강도입니다.\n낮은 값은 끌리는 느낌을 줄입니다. 높은 값은 긁힘 질감을 더 강하게 만듭니다.',
        'shift_delay_ms': '업시프트 이후 가속 펀치 출력이 시작되기 전의 지연 시간입니다.',
        'shift_fade_tail_percent': '업시프트 펀치가 페이드되기 시작한 뒤 남는 잔향 길이입니다. 낮은 값은 꼬리를 빠르게 끊고, 높은 값은 펀치가 더 오래 남습니다.',
        'shift_pulse_boost_ms': '업시프트 지연 후 기어별 감쇠가 적용되기 전에 출력되는 짧은 최대 강도 트리거 펄스입니다.',
        'shift_pulse_lock_ms': '업시프트 지연 후 기어별 감쇠가 적용되기 전에 출력되는 짧은 최대 강도 햅틱 펄스입니다.',
        'shift_wall_fade_percent': '업시프트 저항이 RPM 구간에서 이 지점까지 최대 강도를 유지한 뒤 페이드됩니다. 낮은 값은 잔향 페이드 구간도 짧게 만듭니다.',
        'side_length': '측면 충돌 출력 지속 시간입니다.\n낮은 값은 짧습니다. 높은 값은 더 길게 남깁니다.',
        'side_sensitivity': '측면 충돌 감지 민감도입니다.\n낮은 값은 오탐을 줄입니다. 높은 값은 더 가벼운 측면 접촉도 감지합니다.',
        'slip_drop_low_percent': '슬립 중 남기는 낮은 저항입니다.\n낮은 값은 저항을 더 많이 떨어뜨립니다. 높은 값은 더 많은 저항을 유지합니다.',
        'slip_end_threshold': '슬립 반응이 끝나는 슬립 레벨입니다.\n낮은 값은 더 일찍 회복합니다. 높은 값은 슬립 반응을 더 오래 유지합니다.',
        'slip_influence': '타이어 슬립이 충돌 강도에 기여하는 정도입니다.\n낮은 값은 속도/G-force에 더 의존합니다. 높은 값은 미끄러지는 충돌을 더 강하게 만듭니다.',
        'slip_low_percent': '슬립 중에 남아 있는 저항입니다.\n낮은 값은 슬립 시 트리거가 더 크게 풀리고, 높은 값은 더 단단한 저항을 유지합니다.',
        'slip_pulse_enabled': '이 이펙트의 추가 슬립 펄스 레이어를 켜거나 끕니다.\nOFF에서도 기본 저항은 유지되며 추가 펄스 질감만 제거됩니다.',
        'slip_pulse_end_percent': '슬립 펄스가 상단 범위에 도달하는 출력 레벨입니다.\n낮은 값은 더 빨리 최대 펄스에 도달합니다. 높은 값은 펄스 범위를 더 길게 늘립니다.',
        'slip_pulse_rate': '슬립 펄스의 반복 속도입니다.\n낮은 값은 느리게, 높은 값은 빠르게 펄스합니다.',
        'slip_pulse_start_percent': '슬립 펄스가 시작되는 출력 레벨입니다.\n낮은 값은 더 일찍 펄스합니다. 높은 값은 더 강한 슬립 출력을 기다립니다.',
        'slip_pulse_style': '슬립에 사용할 펄스 방식을 선택합니다.\nSoft Pulse는 부드럽고, Strong Pulse는 선명하며, Pulse Kick은 저항의 세기를 변조합니다.',
        'slip_soft_pulse_amplitude': 'Soft Pulse 출력 강도입니다.\n낮은 값은 미묘합니다. 높은 값은 더 강합니다.',
        'slip_soft_pulse_frequency': 'Soft Pulse 출력 주파수입니다.\n낮은 값은 무겁게, 높은 값은 날카롭게 느껴집니다.',
        'slip_soft_pulse_start_zone': 'Soft Pulse가 시작되는 트리거 구간입니다.\n낮은 값은 더 일찍, 높은 값은 트리거 깊은 쪽에서 시작합니다.',
        'slip_start_offset': '휠스핀 피드백 시작을 앞당기거나 늦춥니다.\n낮은 값은 더 일찍 시작합니다. 높은 값은 더 많은 휠스핀을 기다립니다.',
        'slip_strong_pulse_amplitude': 'Strong Pulse 강도입니다.\n낮은 값은 미묘합니다. 높은 값은 더 강합니다.',
        'slip_strong_pulse_rate': 'Strong Pulse 속도입니다.\n낮은 값은 느리게, 높은 값은 빠르게 펄스합니다.',
        'slip_threshold': '슬립 반응이 시작되는 레벨입니다.\n낮은 값은 더 일찍 반응합니다. 높은 값은 더 큰 슬립을 요구합니다.',
        'small_bump_strength': '작은 요철의 출력 게인입니다.\n낮은 값은 잔질감을 줄입니다. 높은 값은 작은 요철을 더 드러냅니다.',
        'smash_length': '파괴 오브젝트 충돌의 전체 지속 시간입니다.\n낮은 값은 타이트합니다. 높은 값은 더 오래 지속됩니다.',
        'smash_punch': '짧은 첫 타격 강도입니다.\n낮은 값은 틱을 부드럽게 합니다. 높은 값은 오브젝트 충돌을 더 튀게 만듭니다.',
        'smash_sensitivity': '작은 오브젝트 충돌 감지 민감도입니다.\n낮은 값은 사소한 접촉을 무시합니다. 높은 값은 더 많은 파괴 오브젝트 충돌을 감지합니다.',
        'smooth_start_ms': '갑작스러운 저항 변화를 피하기 위한 상승 시간입니다.\n낮은 값은 더 빠르게 반응합니다. 높은 값은 저항이 더 부드럽게 들어옵니다.',
        'speed_drop_threshold': '충돌 감지에 쓰는 속도 손실 기준입니다.\n낮은 값은 작은 충돌도 감지합니다. 높은 값은 더 큰 속도 손실을 요구합니다.',
        'speed_high_max': '속도에 따라 변하는 연석 출력의 고속 기준점입니다.\n낮은 값은 고속 주파수에 더 빨리 도달하고, 높은 값은 더 높은 차량 속도까지 변화 구간을 늘립니다.',
        'speed_low_start': '속도에 따라 변하는 연석 출력의 저속 기준점입니다.\n낮은 값은 속도 매핑을 더 일찍 시작하고, 높은 값은 저속 반응 시작을 늦춥니다.',
        'start_hz': '가속 펀치 시작 부분의 햅틱 주파수입니다.',
        'start_percent': '저항이 시작되는 트리거 위치입니다.\n낮은 값은 더 일찍 저항을 시작합니다. 높은 값은 저항 전 자유 구간을 더 남깁니다.',
        'tail': '주 타격 이후 남는 진동입니다.\n낮은 값은 빠르게 멈춥니다. 높은 값은 잔향을 더 남깁니다.',
        'throttle_pressure': 'Drift Rumble Fade 중 유지할 Throttle Pressure 트리거 레벨입니다.\n낮은 값은 R2 압력을 더 줄입니다. 높은 값은 더 많은 저항을 유지합니다.',
        'throttle_traction': 'Drift Rumble Fade 중 유지할 Throttle Traction 트리거 레벨입니다.\n낮은 값은 트랙션 펄스/저항을 더 많이 줄입니다. 높은 값은 더 많이 유지합니다.',
        'tone': '감각의 주파수와 음색입니다.\n낮은 값은 더 깊고 무겁게, 높은 값은 더 날카롭고 밝게 느껴집니다.',
        'upshift_duration_ms': '업시프트 킥 지속 시간입니다.\n낮은 값은 빠릅니다. 높은 값은 더 오래 지속됩니다.',
        'upshift_strength_percent': '업시프트 킥 강도입니다.\n낮은 값은 부드럽습니다. 높은 값은 변속 킥을 더 강하게 만듭니다.',
        'vehicle_rpm_scaling': '차량별 RPM 특성이 출력에 반영되는 정도입니다.\n낮은 값은 더 균일합니다. 높은 값은 각 차량의 RPM 범위를 더 강하게 따릅니다.',
        'wall_percent': '예측 동작의 강도입니다.\n낮은 값은 보수적입니다. 높은 값은 텔레메트리 기반 저항 이동을 더 적극적으로 만듭니다.',
        'wheelspin_buzz': 'Drift Rumble Fade 중 유지할 휠스핀 햅틱 레벨입니다.\n낮은 값은 휠스핀 버즈를 더 많이 줄입니다. 높은 값은 더 많이 유지합니다.'},
 'CN': {'accel_g_punch': 'Drift Rumble Fade 中保留的加速冲击等级。\n高值在淡出中仍保留更多加速冲击，低值削弱得更积极。',
        'attack': '效果进入的速度。\n低值更柔和，高值更快、更直接。',
        'balance': '调节升挡和降挡反馈的平衡。\n低值更强调降挡，高值更强调升挡。',
        'bump_rejection': '把路面颠簸从侧面碰撞中排除的程度。\n低值允许更多刮擦反应，高值更强过滤路面噪声。',
        'bump_sensitivity': '小路面颠簸的敏感度。\n低值忽略小变化，高值对更细微的路面也反应。',
        'bump_sharpness': '每个路肩凹槽的清晰度。\n低值更柔和，高值让单个纹理更分明。',
        'buzz_hz': '主要空转嗡鸣频率。\n低值更粗、更重，高值更细、更电感。',
        'climb_strength': 'RPM 接近限制器时的累积感。\n低值更平，高值让接近限制器的过程更明显。',
        'condition_strictness': 'Drift Rumble Fade 进入敏感度。\n低值要求更明确、持续的漂移；高值更容易进入淡出。',
        'curve': '从扳机输入到阻力的响应曲线。\n低值更直接、更线性，高值更强烈地改变力度爬升。',
        'decay': '效果消失的速度。\n低值残留更久，高值更快停止。',
        'downshift_duration_ms': '降挡踢感持续时间。\n低值很快，高值更久。',
        'downshift_strength_percent': '降挡踢感强度。\n低值柔和，高值更明显。',
        'downshift_surge': '降挡后 RPM 跳升的追加反应。\n低值减弱冲上来的感觉，高值让降挡补油更明显。',
        'early_input_soft_zone': '让初段扳机输入更柔和。\n低值保持踢感直接，高值在踢感前保留更多软行程。',
        'end_hz': '加速冲击结束部分的触觉频率。',
        'entry_threshold': '抓地极限效果开始的阈值。\n低值更早反应，高值会等轮胎更接近极限。',
        'fade_range': '从开始位置到最大输出的 RPM 范围。\n低值更快上升，高值更渐进。',
        'force_percent': '扳机阻力强度。\n低值更容易按下，高值产生更强阻力墙。',
        'full_load_point': '效果达到最大输出的位置。\n低值更快满强度，高值需要更高轮胎负载。',
        'g_force_threshold': '碰撞检测使用的 G-force 阈值。\n低值检测轻微冲击，高值要求更强冲击。',
        'gear_drop_offset': '高挡输出递减幅度。9 约为 2/3/4 挡 90/80/70，8 会下降得更快。',
        'haptic_gear_1_percent': '1 挡和起步时的触觉输出比例。\n如果希望首次升挡前的起步加速感更强，请保持较高数值。',
        'haptic_gear_2_percent': '2 挡的触觉输出比例。\n如果希望起步到 2 挡的加速感保持连贯，请使用较高数值。',
        'haptic_gear_3_percent': '3 挡的触觉输出基准比例。\n更高挡位的输出会以此数值为基准逐步衰减。',
        'haptic_strength': '加速冲击层的额外触觉增益。\n低值更细微，高值让起步/升挡加速感更明显。',
        'heavy_object_hz': '重物体频率。\n低值更重、更深，高值更尖锐。',
        'high_bump_hz': '小或轻颠簸的频率。\n低值更柔和，高值更尖锐。',
        'high_impact_hz': '轻碰撞频率。\n低值让小碰撞更柔和，高值更清晰。',
        'high_load_hz': '高轮胎负载时的频率。\n低值让受力轮胎更深，高值让极限附近更尖锐。',
        'high_speed_hz': '车辆高速通过路肩时，振动会更快。\n该 Hz 值设置车辆达到最高速度时的振动速率。',
        'howl_amp': 'Shift Down Howl 的 Soft Pulse 振幅。\n数值越低越含蓄；数值越高，Howl 感觉越明显。',
        'howl_duration_ms': 'Shift Down Howl 脉冲的持续时间。\n数值越低越短促紧凑；数值越高，下挡共鸣持续越久。',
        'howl_end_hz': 'Shift Down Howl 结束时的频率。\n数值越低，结束感觉越深沉；数值越高，越尖锐。',
        'howl_noise_percent': 'Howl 淡出时混入频率和强度的噪声。\n数值越低越干净；数值越高，感觉越粗糙、越不规则。',
        'howl_start_hz': 'Shift Down Howl 开始时的频率。\n数值越低，起始感觉越深沉；数值越高，越尖锐。',
        'howl_start_zone': 'Shift Down Howl 的 Soft Pulse 起始位置。\n数值越低开始越早；数值越高，起点越深入扳机行程。',
        'impact_length': '碰撞反馈持续时间。\n低值更快，高值更持久。',
        'impact_punch': '碰撞第一下冲击强度。\n低值更柔和，高值更突然。',
        'kerb_high_hz': '车辆高速通过路肩时，振动会更快。\n该 Hz 值设置车辆达到最高速度时的振动速率。',
        'kerb_l_enabled': '启用或禁用 Kerb Wave 的 L2 输出。\n关闭 L2 不会禁用共享设置或 R2 输出。',
        'kerb_l_high_amp': '车辆高速时 L2 与 R2 共用的 Soft Pulse 振幅。\n数值越低越柔和，数值越高越强。',
        'kerb_l_low_amp': '车辆低速时 L2 与 R2 共用的 Soft Pulse 振幅。\n数值越低越柔和，数值越高越强。',
        'kerb_l_start_percent': 'L2 与 R2 共用的 Soft Pulse 起始位置。\n数值越低，脉冲开始越早；数值越高，起始位置越深入扳机行程。',
        'kerb_low_hz': '设置车辆低速行驶时的路肩振动速率。\n车辆速度较低时，路肩振动不应设置得过快。',
        'kerb_r_enabled': '启用或禁用 Kerb Wave 的 R2 输出。\n关闭 R2 不会禁用共享设置或 L2 输出。',
        'kick_late_position': '踢感到达得更晚的位置。\n低值提前踢感，高值推向扳机更深处。',
        'kick_softness': '踢感的锐利或柔软程度。\n低值更尖锐，高值更缓冲。',
        'kick_strong_pulse_duration_ms': 'Howl 前短促 Kick Soft Pulse 的持续时间。\n数值越低越短促紧凑；数值越高，Kick 持续越久。',
        'kick_strong_pulse_hz': 'Howl 前短促 Kick Soft Pulse 的频率。\n数值越低越深沉；数值越高越尖锐。',
        'kick_strong_pulse_strength': 'Howl 前短促 Kick Soft Pulse 的强度。\n数值越低越柔和；数值越高，下挡接合感越明显。',
        'large_bump_strength': '大颠簸输出增益。\n低值让大冲击更柔和，高值让重颠簸更强。',
        'launch_wall_fade_percent': '起步阻力在 RPM 区间中保持最大强度到此比例后开始淡出。',
        'length': '冲击的整体持续时间。\n低值短而紧，高值更长、更持续。',
        'light_object_hz': '轻物体频率。\n低值更柔和，高值更清晰。',
        'low_bump_hz': '大或重颠簸的频率。\n低值更深，高值更紧。',
        'low_class_correction': '面向较慢或低等级车辆的补偿。\n低值接近原始输出，高值让低速车辆也更容易感觉到。',
        'low_impact_hz': '强碰撞频率。\n低值深而重，高值更尖锐。',
        'low_load_hz': '低轮胎负载时的频率。\n低值更重，高值让进入感更亮。',
        'low_speed_hz': '设置车辆低速行驶时的路肩振动速率。\n车辆速度较低时，路肩振动不应设置得过快。',
        'max_gear_limit': '用于减少最高挡疲劳感的限制。\n低值保留更多高挡震动，高值进一步减少持续嗡鸣。',
        'max_percent': '阻力达到最大的位置。\n低值让阻力墙更靠前，高值把墙移到更深处。',
        'max_rpm_offset': '输出区间偏移。10 表示 1 挡到 100% max RPM，2 挡到 90%。',
        'noise_range': '嗡鸣频率周围的随机变化范围。\n低值更稳定，高值增加更多随机纹理。',
        'pan': '把输出分配到左/右触觉通道。\n5 为居中；低值偏左，高值偏右。',
        'pulse_gear_1_percent': '1 挡和起步时 Soft/Strong Pulse 的输出比例。\n若希望首次升挡前有强烈的起步反馈，请保持较高数值。',
        'pulse_gear_2_percent': '2 挡的 Soft/Strong Pulse 输出比例。\n若希望起步与 2 挡之间的反馈连续，请使用较高数值。',
        'pulse_gear_3_percent': '3 挡的 Soft/Strong Pulse 基准输出比例。\n更高挡位会从此数值开始衰减。',
        'pulse_rate': '脉冲或抖动速度。\n低值慢而重，高值更快、更敏感。',
        'pulse_start_percent': '脉冲开始的位置。\n低值更早开始，高值延后到区间后段。',
        'pulse_strength': '扳机脉冲反应强度。\n低值更细微，高值更容易感觉到。',
        'punch': '第一下冲击的强度。\n低值更柔和，高值让咬合感更硬。',
        'rattle_strength': '碎片和余震强度。\n低值减少后续抖动，高值增加破碎质感。',
        'release_duration_ms': '踢感后的释放时间。\n低值快速释放，高值逐渐消失。',
        'repeat_cooldown': '重复小物体碰撞之间的最短间隔。\n低值允许快速连续 tick，高值避免输出过密。',
        'rpm_position': '效果开始的 RPM 位置。\n数值越低开始越早；数值越高，输出会延迟到更接近红线时开始。',
        'rpm_rev_limit': 'Drift Rumble Fade 中保留的 RPM Rev Limit 扳机等级。\n低值更多减少限制器扳机输出，高值保留更多。',
        'scrape_strength': '刮擦/车身接触强度。\n低值减少拖拽感，高值强化刮擦纹理。',
        'shift_delay_ms': '升挡后加速冲击开始前的延迟时间。',
        'shift_fade_tail_percent': '升挡冲击开始淡出后残留尾部的长度。低值会快速切断尾部，高值会让冲击保留更久。',
        'shift_pulse_boost_ms': '升挡延迟后、应用挡位衰减前输出的短促全强度扳机脉冲。',
        'shift_pulse_lock_ms': '升挡延迟后、应用挡位衰减前输出的短促全强度触觉脉冲。',
        'shift_wall_fade_percent': '升挡阻力在 RPM 区间中保持最大强度到此比例后开始淡出。较低值也会缩短残留淡出尾部。',
        'side_length': '侧面碰撞输出持续时间。\n低值较短，高值更久。',
        'side_sensitivity': '侧面碰撞检测敏感度。\n低值减少误触发，高值会检测更轻的侧面接触。',
        'slip_drop_low_percent': '滑移时保留的低阻力。\n低值阻力下降更多，高值保留更多阻力。',
        'slip_end_threshold': '滑移反应结束的滑移等级。\n低值更早恢复，高值让反应保持更久。',
        'slip_influence': '轮胎滑移对碰撞强度的贡献。\n低值更依赖速度/G-force，高值让滑着撞的情况更强。',
        'slip_low_percent': '发生打滑时保留的阻力。\n数值越低，打滑时扳机释放越明显；数值越高，保留的阻力越强。',
        'slip_pulse_enabled': '启用或禁用此效果的附加打滑脉冲层。\n关闭后仍保留基础阻力，只移除额外的脉冲纹理。',
        'slip_pulse_end_percent': '滑移脉冲达到上限范围的输出等级。\n低值更快到最大，高值拉长脉冲范围。',
        'slip_pulse_rate': '打滑脉冲的重复速率。\n数值越低脉冲越慢；数值越高越快。',
        'slip_pulse_start_percent': '滑移脉冲开始的输出等级。\n低值更早脉冲，高值等待更强滑移输出。',
        'slip_pulse_style': '选择打滑使用的脉冲方式。\nSoft Pulse 更平滑，Strong Pulse 更清晰，Pulse Kick 会调制阻力强度。',
        'slip_soft_pulse_amplitude': 'Soft Pulse 输出强度。\n低值更细微，高值更强。',
        'slip_soft_pulse_frequency': 'Soft Pulse 输出频率。\n低值更重，高值更尖锐。',
        'slip_soft_pulse_start_zone': 'Soft Pulse 开始的扳机区间。\n低值更早，高值更靠深处。',
        'slip_start_offset': '提前或延后空转反馈开始点。\n低值更早开始，高值等待更多空转。',
        'slip_strong_pulse_amplitude': 'Strong Pulse 强度。\n低值更细微，高值更强。',
        'slip_strong_pulse_rate': 'Strong Pulse 速度。\n低值更慢，高值更快。',
        'slip_threshold': '滑移反应开始的等级。\n低值更早反应，高值需要更大滑移。',
        'small_bump_strength': '小颠簸输出增益。\n低值减少细碎质感，高值让小颠簸更突出。',
        'smash_length': '可破坏物体碰撞的整体持续时间。\n低值更紧，高值更长。',
        'smash_punch': '短促第一下冲击强度。\n低值更柔和，高值让物体碰撞更弹。',
        'smash_sensitivity': '小物体碰撞检测敏感度。\n低值忽略小接触，高值检测更多可破坏物体。',
        'smooth_start_ms': '避免阻力突然变化的上升时间。\n低值反应更快，高值进入更平滑。',
        'speed_drop_threshold': '碰撞检测使用的速度损失阈值。\n低值会检测较小碰撞，高值要求更大的速度损失。',
        'speed_high_max': '随速度映射的路肩输出高速度参考点。\n数值越低越早达到高速频率；数值越高，变化范围延伸到更高车速。',
        'speed_low_start': '随速度映射的路肩输出低速度参考点。\n数值越低越早开始速度映射；数值越高，低速响应开始越晚。',
        'start_hz': '加速冲击开始部分的触觉频率。',
        'start_percent': '阻力开始的扳机位置。\n低值更早开始阻力，高值保留更多自由行程。',
        'tail': '主冲击之后残留的振动。\n低值更快停止，高值留下更多余韵。',
        'throttle_pressure': 'Drift Rumble Fade 中保留的 Throttle Pressure 扳机等级。\n低值减少更多 R2 压力，高值保留更多阻力。',
        'throttle_traction': 'Drift Rumble Fade 中保留的 Throttle Traction 扳机等级。\n低值减少更多牵引脉冲/阻力，高值保留更多。',
        'tone': '反馈的频率和音色。\n低值更深、更重；高值更尖锐、更明亮。',
        'upshift_duration_ms': '升挡踢感持续时间。\n低值很快，高值更久。',
        'upshift_strength_percent': '升挡踢感强度。\n低值柔和，高值更强。',
        'vehicle_rpm_scaling': '车辆自身 RPM 特性参与输出的程度。\n低值更统一，高值更贴合每台车的 RPM 范围。',
        'wall_percent': '预测动作强度。\n低值更保守，高值更主动移动遥测驱动的阻力。',
        'wheelspin_buzz': 'Drift Rumble Fade 中保留的轮胎空转触觉等级。\n低值会更多削弱空转嗡鸣，高值保留更多。'},
 'ES': {'accel_g_punch': 'Nivel de Acceleration G Punch conservado durante Drift Rumble Fade.\n'
                         'Valores altos mantienen más golpe; bajos lo reducen más agresivamente.',
        'attack': 'Velocidad con la que entra el efecto.\nValores bajos entran suave; altos responden más rápido.',
        'balance': 'Equilibra la sensación entre subida y bajada de marcha.\n'
                   'Valores bajos favorecen downshift; altos favorecen upshift.',
        'bump_rejection': 'Filtra los baches de la deteccion de impactos laterales.\n'
                          'Los valores bajos permiten mas activaciones por roce; los altos rechazan con mayor intensidad el ruido '
                          'de los baches.',
        'bump_sensitivity': 'Sensibilidad a baches pequeños.\nValores bajos ignoran cambios leves; altos reaccionan a más detalle.',
        'bump_sharpness': 'Claridad de cada irregularidad del piano.\nValores bajos suavizan; altos separan mejor cada ranura.',
        'buzz_hz': 'Frecuencia principal del zumbido de wheelspin.\nValores bajos son ásperos y pesados; altos más finos.',
        'climb_strength': 'Acumulación al subir hacia el limitador.\n'
                          'Valores bajos son más planos; altos marcan mejor el acercamiento.',
        'condition_strictness': 'Sensibilidad de entrada a Drift Rumble Fade.\n'
                                'Valores bajos exigen drift más claro y sostenido; altos entran más fácilmente.',
        'curve': 'Curva entre entrada del gatillo y resistencia.\n'
                 'Valores bajos son más directos; altos modifican más la rampa de fuerza.',
        'decay': 'Velocidad con la que desaparece el efecto.\nValores bajos duran más; altos se detienen antes.',
        'downshift_duration_ms': 'Duración de la patada al bajar marcha.\nValores bajos son rápidos; altos duran más.',
        'downshift_strength_percent': 'Fuerza de la patada al bajar marcha.\nValores bajos son suaves; altos golpean más.',
        'downshift_surge': 'Respuesta extra tras un salto de RPM al bajar marcha.\n'
                           'Valores bajos la reducen; altos la hacen más clara.',
        'early_input_soft_zone': 'Suaviza la zona inicial del recorrido del gatillo.\n'
                                 'Los valores bajos mantienen la patada inmediata; los altos dejan mas recorrido suave antes de la '
                                 'patada.',
        'end_hz': 'Frecuencia háptica al final de acceleration punch.',
        'entry_threshold': 'Punto donde empieza el efecto de límite de agarre.\n'
                           'Valores bajos reaccionan antes; altos esperan a estar más cerca del límite.',
        'fade_range': 'Rango de RPM desde el inicio hasta la salida máxima.\n'
                      'Valores bajos suben rápido; altos acumulan de forma gradual.',
        'force_percent': 'Fuerza de resistencia del gatillo.\n'
                         'Valores bajos son fáciles de pulsar; altos crean una pared más fuerte.',
        'full_load_point': 'Punto donde el efecto llega a salida máxima.\n'
                           'Valores bajos llegan antes; altos requieren más carga de neumático.',
        'g_force_threshold': 'Umbral de G-force para impacto.\n'
                             'Valores bajos detectan impactos ligeros; altos exigen impactos fuertes.',
        'gear_drop_offset': 'Caída de salida en marchas superiores. 9 produce aprox. 90/80/70; 8 cae más rápido.',
        'haptic_gear_1_percent': 'Escala de salida haptica para 1.ª marcha y salida.\n'
                                 'Mantenla alta si la aceleracion debe sentirse fuerte antes del primer cambio ascendente.',
        'haptic_gear_2_percent': 'Escala de salida haptica para 2.ª marcha.\n'
                                 'Usa un valor alto si la salida y la 2.ª marcha deben sentirse continuas.',
        'haptic_gear_3_percent': 'Escala base de salida haptica para 3.ª marcha.\n'
                                 'Las marchas superiores reducen su salida a partir de este valor.',
        'haptic_strength': 'Ganancia extra de la capa de acceleration punch.\n'
                           'Valores bajos son sutiles; altos hacen más evidente salida y aceleración.',
        'heavy_object_hz': 'Frecuencia para objetos pesados.\n'
                           'Los valores bajos se sienten mas pesados y profundos; los altos hacen los golpes pesados mas afilados.',
        'high_bump_hz': 'Frecuencia para baches pequenos o ligeros.\n'
                        'Los valores bajos se sienten mas suaves; los altos, mas afilados.',
        'high_impact_hz': 'Frecuencia para impactos ligeros.\n'
                          'Los valores bajos suavizan los golpes pequenos; los altos los hacen mas nitidos.',
        'high_load_hz': 'Frecuencia con alta carga de neumático.\n'
                        'Valores bajos son más profundos; altos hacen el límite más agudo.',
        'high_speed_hz': 'Cuando el vehículo pasa por el piano a alta velocidad, la vibración es más rápida.\n'
                         'El valor en Hz define la velocidad de vibración a la velocidad máxima del vehículo.',
        'howl_amp': 'Amplitud de Soft Pulse para Shift Down Howl.\n'
                    'Los valores bajos son sutiles; los altos hacen que el Howl se perciba con mayor claridad.',
        'howl_duration_ms': 'Duracion del pulso de Shift Down Howl.\n'
                            'Los valores bajos son cortos y firmes; los altos mantienen mas tiempo la resonancia de la reduccion.',
        'howl_end_hz': 'Frecuencia final de Shift Down Howl.\nLos valores bajos terminan mas profundos; los altos, mas afilados.',
        'howl_noise_percent': 'Ruido de frecuencia e intensidad durante el desvanecimiento del Howl.\n'
                              'Los valores bajos son mas limpios; los altos se sienten mas asperos e irregulares.',
        'howl_start_hz': 'Frecuencia inicial de Shift Down Howl.\n'
                         'Los valores bajos empiezan mas profundos; los altos, mas afilados.',
        'howl_start_zone': 'Posicion inicial de Soft Pulse para Shift Down Howl.\n'
                           'Los valores bajos empiezan antes; los altos desplazan el inicio mas adentro del recorrido.',
        'impact_length': 'Duración del impacto.\nValores bajos son rápidos; altos duran más.',
        'impact_punch': 'Fuerza del primer golpe de impacto.\nValores bajos suavizan; altos lo hacen más repentino.',
        'kerb_high_hz': 'Cuando el vehículo pasa por el piano a alta velocidad, la vibración es más rápida.\n'
                        'El valor en Hz define la velocidad de vibración a la velocidad máxima del vehículo.',
        'kerb_l_enabled': 'Activa o desactiva la salida Kerb Wave en L2.\n'
                          'Desactivar L2 no desactiva los ajustes compartidos ni la salida R2.',
        'kerb_l_high_amp': 'Amplitud Soft Pulse compartida por L2 y R2 a alta velocidad.\n'
                           'Los valores bajos son más suaves; los altos son más fuertes.',
        'kerb_l_low_amp': 'Amplitud Soft Pulse compartida por L2 y R2 a baja velocidad.\n'
                          'Los valores bajos son más suaves; los altos son más fuertes.',
        'kerb_l_start_percent': 'Posición inicial de Soft Pulse compartida por L2 y R2.\n'
                                'Los valores bajos empiezan antes; los altos desplazan el inicio más adentro del recorrido.',
        'kerb_low_hz': 'Define la velocidad de vibración del piano cuando el vehículo circula a baja velocidad.\n'
                       'A baja velocidad, la vibración del piano no debe ser demasiado rápida.',
        'kerb_r_enabled': 'Activa o desactiva la salida Kerb Wave en R2.\n'
                          'Desactivar R2 no desactiva los ajustes compartidos ni la salida L2.',
        'kick_late_position': 'Posicion en la que llega la patada tardia.\n'
                              'Los valores bajos adelantan la patada; los altos la desplazan mas adentro del recorrido del '
                              'gatillo.',
        'kick_softness': 'Suavidad o nitidez de la patada.\n'
                         'Los valores bajos se sienten mas afilados; los altos, mas amortiguados.',
        'kick_strong_pulse_duration_ms': 'Duracion del breve Kick Soft Pulse anterior al Howl.\n'
                                         'Los valores bajos son cortos y firmes; los altos mantienen mas tiempo la patada.',
        'kick_strong_pulse_hz': 'Frecuencia del breve Kick Soft Pulse anterior al Howl.\n'
                                'Los valores bajos se sienten mas profundos; los altos, mas afilados.',
        'kick_strong_pulse_strength': 'Fuerza del breve Kick Soft Pulse anterior al Howl.\n'
                                      'Los valores bajos son suaves; los altos hacen mas evidente el acoplamiento de la reduccion.',
        'large_bump_strength': 'Ganancia de baches grandes.\nValores bajos suavizan impactos; altos los hacen más fuertes.',
        'launch_wall_fade_percent': 'Punto del rango RPM donde la pared de salida empieza a desvanecerse.',
        'length': 'Duración total del golpe.\nValores bajos son cortos y secos; altos duran más.',
        'light_object_hz': 'Frecuencia para objetos ligeros.\n'
                           'Los valores bajos suavizan los golpes ligeros; los altos los hacen mas nitidos.',
        'low_bump_hz': 'Frecuencia para baches grandes o pesados.\n'
                       'Los valores bajos se sienten mas profundos; los altos, mas firmes.',
        'low_class_correction': 'Corrección para coches lentos o de clase baja.\n'
                                'Valores bajos son más originales; altos hacen que se sientan más fácilmente.',
        'low_impact_hz': 'Frecuencia para impactos fuertes.\n'
                         'Los valores bajos se sienten mas profundos y pesados; los altos, mas afilados.',
        'low_load_hz': 'Frecuencia con baja carga de neumático.\nValores bajos pesan más; altos hacen la entrada más brillante.',
        'low_speed_hz': 'Define la velocidad de vibración del piano cuando el vehículo circula a baja velocidad.\n'
                        'A baja velocidad, la vibración del piano no debe ser demasiado rápida.',
        'max_gear_limit': 'Reduce fatiga en la marcha más alta.\nValores bajos conservan más zumbido; altos lo reducen más.',
        'max_percent': 'Posición donde la resistencia llega al máximo.\n'
                       'Valores bajos adelantan la pared; altos la llevan más profundo.',
        'max_rpm_offset': 'Offset del rango de salida. 10 significa 1ª a 100% max RPM y 2ª a 90%.',
        'noise_range': 'Variación alrededor de la frecuencia de buzz.\nValores bajos son estables; altos añaden textura aleatoria.',
        'pan': 'Coloca la salida entre los canales hápticos izquierdo y derecho.\n'
               '5 es centro; valores bajos favorecen izquierda y altos derecha.',
        'pulse_gear_1_percent': 'Escala de salida Soft/Strong Pulse para 1.ª marcha y salida.\n'
                                'Mantenla alta si deseas una respuesta de salida fuerte antes del primer cambio ascendente.',
        'pulse_gear_2_percent': 'Escala de salida Soft/Strong Pulse para 2.ª marcha.\n'
                                'Usa un valor alto si la salida y la 2.ª marcha deben sentirse continuas.',
        'pulse_gear_3_percent': 'Escala base de salida Soft/Strong Pulse para 3.ª marcha.\n'
                                'Las marchas superiores reducen su salida a partir de este valor.',
        'pulse_rate': 'Velocidad de pulso o chatter.\nValores bajos son lentos y pesados; altos son rápidos y sensibles.',
        'pulse_start_percent': 'Posición donde empieza el pulso.\nValores bajos empiezan antes; altos retrasan el pulso.',
        'pulse_strength': 'Fuerza de la reacción de pulso del gatillo.\n'
                          'Valores bajos son sutiles; altos se sienten más fácilmente.',
        'punch': 'Fuerza del primer golpe.\nValores bajos suavizan el impacto; altos hacen la mordida más firme.',
        'rattle_strength': 'Fuerza del cuerpo de residuos y traqueteo.\n'
                           'Los valores bajos reducen el traqueteo posterior; los altos anaden mas textura de objeto roto.',
        'release_duration_ms': 'Tiempo de liberacion despues de la patada.\n'
                               'Los valores bajos liberan rapido; los altos dejan que la patada se desvanezca.',
        'repeat_cooldown': 'Tiempo minimo entre impactos repetidos de objetos rompibles.\n'
                           'Los valores bajos permiten tics rapidos; los altos evitan una salida repetida demasiado densa.',
        'rpm_position': 'Punto de RPM en el que empieza el efecto.\n'
                        'Los valores bajos empiezan antes; los altos retrasan la salida hasta acercarse a la linea roja.',
        'rpm_rev_limit': 'Nivel de RPM Rev Limit conservado durante Drift Rumble Fade.\n'
                         'Valores bajos reducen más la salida; altos conservan más.',
        'scrape_strength': 'Fuerza de la parte de roce y carroceria.\n'
                           'Los valores bajos reducen la sensacion de arrastre; los altos dan mas textura al roce.',
        'shift_delay_ms': 'Retardo después del upshift antes de iniciar acceleration punch.',
        'shift_fade_tail_percent': 'Longitud de la cola residual después de que empieza el fade del golpe de upshift. Valores '
                                   'bajos cortan antes; altos dejan más permanencia.',
        'shift_pulse_boost_ms': 'Pulso breve del gatillo a fuerza maxima despues del retraso de subida y antes de aplicar la '
                                'reduccion por marcha.',
        'shift_pulse_lock_ms': 'Pulso haptico breve a fuerza maxima despues del retraso de subida y antes de aplicar la reduccion '
                               'por marcha.',
        'shift_wall_fade_percent': 'Punto del rango RPM donde la pared tras upshift empieza a desvanecerse. Valores bajos también '
                                   'acortan la cola del fade.',
        'side_length': 'Duracion de la salida por impacto lateral.\n'
                       'Los valores bajos producen golpes cortos; los altos dejan una cola mas larga.',
        'side_sensitivity': 'Sensibilidad de deteccion de impactos laterales.\n'
                            'Los valores bajos reducen falsos positivos; los altos detectan contactos laterales mas leves.',
        'slip_drop_low_percent': 'Resistencia baja restante durante el deslizamiento.\n'
                                 'Los valores bajos reducen mas la resistencia; los altos conservan mas resistencia.',
        'slip_end_threshold': 'Nivel donde termina la reacción de slip.\n'
                              'Valores bajos recuperan antes; altos mantienen la reacción más tiempo.',
        'slip_influence': 'Contribucion del deslizamiento de los neumaticos a la fuerza del impacto.\n'
                          'Los valores bajos dependen mas de la velocidad y la fuerza G; los altos refuerzan los impactos en '
                          'deslizamiento.',
        'slip_low_percent': 'Resistencia que permanece durante el deslizamiento.\n'
                            'Los valores bajos liberan mas el gatillo; los altos lo mantienen mas firme.',
        'slip_pulse_enabled': 'Activa o desactiva la capa adicional de pulsos de deslizamiento.\n'
                              'OFF conserva la resistencia base y elimina solo la textura de pulso adicional.',
        'slip_pulse_end_percent': 'Nivel de salida en el que los pulsos de deslizamiento alcanzan su zona superior.\n'
                                  'Los valores bajos llegan antes al pulso maximo; los altos amplian el rango.',
        'slip_pulse_rate': 'Velocidad de repeticion del pulso de deslizamiento.\n'
                           'Los valores bajos pulsan mas despacio; los altos, mas rapido.',
        'slip_pulse_start_percent': 'Nivel de salida en el que empiezan los pulsos de deslizamiento.\n'
                                    'Los valores bajos empiezan antes; los altos esperan una senal de deslizamiento mas fuerte.',
        'slip_pulse_style': 'Selecciona el metodo de pulso para el deslizamiento.\n'
                            'Soft Pulse es mas suave, Strong Pulse mas marcado y Pulse Kick modula la fuerza de resistencia.',
        'slip_soft_pulse_amplitude': 'Fuerza de salida Soft Pulse.\nValores bajos son sutiles; altos más fuertes.',
        'slip_soft_pulse_frequency': 'Frecuencia de Soft Pulse.\nValores bajos son graves; altos más agudos.',
        'slip_soft_pulse_start_zone': 'Zona del gatillo donde empieza Soft Pulse.\n'
                                      'Valores bajos empiezan antes; altos más profundo.',
        'slip_start_offset': 'Adelanta o retrasa el inicio del feedback de wheelspin.\n'
                             'Valores bajos empiezan antes; altos esperan más patinaje.',
        'slip_strong_pulse_amplitude': 'Fuerza de Strong Pulse.\nValores bajos son sutiles; altos más fuertes.',
        'slip_strong_pulse_rate': 'Velocidad de Strong Pulse.\nValores bajos son lentos; altos más rápidos.',
        'slip_threshold': 'Nivel donde empieza la reacción de slip.\nValores bajos reaccionan antes; altos requieren más slip.',
        'small_bump_strength': 'Ganancia de baches pequeños.\nValores bajos reducen textura fina; altos la resaltan.',
        'smash_length': 'Duracion total del impacto contra objetos rompibles.\n'
                        'Los valores bajos son mas cortos y firmes; los altos duran mas.',
        'smash_punch': 'Fuerza del primer golpe corto.\n'
                       'Los valores bajos suavizan el tic; los altos hacen resaltar el impacto del objeto.',
        'smash_sensitivity': 'Sensibilidad para detectar golpes contra objetos pequenos.\n'
                             'Los valores bajos ignoran contactos leves; los altos detectan mas objetos rompibles.',
        'smooth_start_ms': 'Tiempo de entrada para evitar cambios bruscos.\n'
                           'Valores bajos reaccionan rápido; altos entran más suave.',
        'speed_drop_threshold': 'Pérdida de velocidad usada para detectar impacto.\n'
                                'Valores bajos detectan golpes pequeños; altos exigen mayor pérdida.',
        'speed_high_max': 'Punto de referencia de alta velocidad para la salida de piano mapeada por velocidad.\n'
                          'Los valores bajos alcanzan antes la frecuencia alta; los altos extienden el rango hasta velocidades '
                          'mayores.',
        'speed_low_start': 'Punto de referencia de baja velocidad para la salida de piano mapeada por velocidad.\n'
                           'Los valores bajos inician antes el mapeo; los altos retrasan la respuesta de baja velocidad.',
        'start_hz': 'Frecuencia háptica al inicio de acceleration punch.',
        'start_percent': 'Posición donde empieza la resistencia.\nValores bajos empiezan antes; altos dejan más recorrido libre.',
        'tail': 'Vibración restante después del golpe principal.\nValores bajos se apagan rápido; altos dejan más cola.',
        'throttle_pressure': 'Nivel de Throttle Pressure conservado durante Drift Rumble Fade.\n'
                             'Valores bajos reducen más la presión R2; altos conservan más resistencia.',
        'throttle_traction': 'Nivel de Throttle Traction conservado durante Drift Rumble Fade.\n'
                             'Valores bajos reducen más pulso/resistencia; altos conservan más.',
        'tone': 'Frecuencia y color de la sensación.\nValores bajos se sienten más profundos; altos más agudos.',
        'upshift_duration_ms': 'Duración de la patada al subir marcha.\nValores bajos son rápidos; altos duran más.',
        'upshift_strength_percent': 'Fuerza de la patada al subir marcha.\nValores bajos son suaves; altos más fuertes.',
        'vehicle_rpm_scaling': 'Cuánto influyen las RPM propias de cada coche.\n'
                               'Valores bajos son más uniformes; altos siguen más el rango de cada vehículo.',
        'wall_percent': 'Fuerza del comportamiento predictivo.\n'
                        'Valores bajos son conservadores; altos mueven más la resistencia con telemetría.',
        'wheelspin_buzz': 'Nivel de Wheelspin Buzz conservado durante Drift Rumble Fade.\n'
                          'Valores bajos reducen más el buzz; altos conservan más.'}}
