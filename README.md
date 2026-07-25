# 노부나가의 야망 DS 2 한글패치 (Nobunaga no Yabou DS 2 Korean Patch)

코에이 **노부나가의 야망 DS 2** (信長の野望DS 2, 2008, CN2J)의 비공식 한글화 패치입니다.

## 특징

- 게임 내 12×12 비트맵 폰트를 **갈무리11**(Galmuri) 한글 폰트로 교체
- 대사·이벤트·메뉴 설명·튜토리얼·무장 열전 등 msgsec 텍스트 전체 번역 (약 10,000 유닛 / 원문 267KB)
- 무장/지명/성/가보/스킬 이름 데이터베이스(common.snr) 음역 및 번역
- ARM9 내장 시스템 메시지 번역
- **v1.2**: msgsec 리빌드로 파일 내부 공간을 재분배해 번역 품질을 개선하면서도,
  파일 크기와 ROM 레이아웃은 원본과 완전히 동일하게 유지 (v1.1의 진행 중 멈춤 현상 수정)

## 적용 방법

1. 본인이 소유한 **일본판 ROM**을 준비합니다.
   - 파일명 예: `Nobunaga no Yabou DS 2 (Japan).nds`
   - 원본 CRC32: `72C536BA` / 패치 후 CRC32(v1.1): `5C1D292C`
2. xdelta 패치 적용 도구를 사용해 `nobu2-kr.xdelta`를 적용합니다.
   - Windows: xdeltaUI 또는 [xdelta3](https://github.com/jmacd/xdelta) 명령행:
     ```
     xdelta3 -d -s "원본.nds" nobu2-kr.xdelta "한글판.nds"
     ```
   - 웹: [RomPatcher.js](https://www.marcrobledo.com/RomPatcher.js/) (xdelta 지원)
3. 생성된 ROM을 melonDS / DeSmuME 등 에뮬레이터 또는 실기에서 구동합니다.

## 알려진 제한 사항

- 타이틀 화면·메뉴 버튼 등 **그래픽으로 그려진 텍스트**는 일본어로 남아 있습니다.
- 신무장 작성 시 한자 입력기는 한글 음절 선택기로 동작합니다(폰트 교체의 부수 효과).
- 일부 바이트 예산이 극히 작은 조사(1바이트)는 공백으로 처리되어 문장이 살짝 축약될 수 있습니다.
- Wi-Fi(WFC) 관련 화면은 서비스 종료로 검증되지 않았습니다.

## 기술 정보

- 폰트: ARM9 내장 12×12 1bpp 연속 패킹 폰트(3,574 글리프), SJIS→글리프 룩업 테이블 리버싱
- 한글 인코딩: 한자 글리프 슬롯(3,200여 개)에 사용 음절을 동적 할당하는 방식
- 자세한 기술 문서와 도구는 `tools/` 참조

## 라이선스 / 고지

- 이 저장소는 **패치 파일과 도구만** 포함하며 게임 데이터(ROM)는 포함하지 않습니다.
- 게임 저작권은 KOEI(現 코에이테크모)에 있습니다. 패치 적용은 본인 소유 사본에만 하십시오.
- 한글 폰트: [Galmuri](https://github.com/quiple/galmuri) (SIL OFL 1.1)
- 번역·패치 도구: Claude (Anthropic) 협업으로 제작
