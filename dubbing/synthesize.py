#!/usr/bin/env python3
"""강의 더빙 합성 파이프라인.

대본 텍스트 파일을 참조 음성(교수자 목소리)으로 클로닝하여 더빙 오디오를
생성한다. 모델은 Chatterbox Multilingual(MIT 라이선스, 23개 언어)을 사용한다.

대본 형식 (UTF-8 텍스트):
  - 한 줄 = 한 문장 (문장 단위 합성이 품질과 재시도에 유리)
  - 빈 줄 = 문단 쉼 (--paragraph-pause 초)
  - '#'로 시작하는 줄 = 주석 (무시)

사용 예:
  python synthesize.py --script week01/video1/script_en.txt \
      --ref ref/joocheol_ref.wav --lang en --out out/week01_v1_en.wav

재실행 시 이미 합성된 문장 조각(work 디렉터리의 캐시)은 건너뛰므로,
중단된 작업을 그대로 이어서 돌릴 수 있다. 문장 텍스트가 바뀌면 해시가
달라져 자동으로 다시 합성된다.
"""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_LANGS = (
    "ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh"
).split()

PUNCT_SPLIT = re.compile(r"(?<=[.!?。！？;；])\s+")


def load_units(script_path: Path):
    """대본을 (kind, payload) 목록으로 파싱한다. kind는 text 또는 pause."""
    units = []
    for raw in script_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            if units and units[-1][0] == "text":
                units.append(("pause", None))
            continue
        if line.startswith("#"):
            continue
        units.append(("text", line))
    return units


def split_long(text: str, max_chars: int) -> list[str]:
    """너무 긴 문장을 구두점 기준으로 나눈다."""
    if len(text) <= max_chars:
        return [text]
    parts, buf = [], ""
    for piece in PUNCT_SPLIT.split(text):
        if buf and len(buf) + len(piece) + 1 > max_chars:
            parts.append(buf)
            buf = piece
        else:
            buf = f"{buf} {piece}".strip()
    if buf:
        parts.append(buf)
    return parts


def seg_name(idx: int, text: str, lang: str, ref: Path) -> str:
    h = hashlib.sha1(f"{lang}|{ref.name}|{text}".encode()).hexdigest()[:12]
    return f"{idx:04d}_{h}.wav"


def loudnorm(src: Path, dst: Path) -> bool:
    """ffmpeg이 있으면 방송 표준(-16 LUFS)으로 음량 정규화한다."""
    if shutil.which("ffmpeg") is None:
        return False
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src),
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    if dst.suffix == ".m4a":
        cmd += ["-c:a", "aac", "-b:a", "160k"]
    cmd.append(str(dst))
    return subprocess.run(cmd).returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True, type=Path, help="대본 텍스트 파일")
    ap.add_argument("--ref", required=True, type=Path, help="참조 음성 wav (10~20초, 모노 권장)")
    ap.add_argument("--lang", required=True, choices=SUPPORTED_LANGS, help="합성 언어")
    ap.add_argument("--out", required=True, type=Path, help="출력 파일 (.wav 또는 .m4a)")
    ap.add_argument("--work", type=Path, default=None,
                    help="문장 조각 캐시 디렉터리 (기본: <out>.segments)")
    ap.add_argument("--pause", type=float, default=0.45, help="문장 사이 쉼(초)")
    ap.add_argument("--paragraph-pause", type=float, default=0.95, help="문단 사이 쉼(초)")
    ap.add_argument("--max-chars", type=int, default=250, help="문장 분할 길이 상한")
    ap.add_argument("--exaggeration", type=float, default=0.5, help="억양 과장 정도(0~1)")
    ap.add_argument("--cfg-weight", type=float, default=0.5, help="참조 음성 반영 강도")
    ap.add_argument("--retries", type=int, default=3, help="문장별 합성 재시도 횟수")
    ap.add_argument("--seed", type=int, default=1234, help="난수 시드 (재현성)")
    ap.add_argument("--device", default=None, help="cuda / cpu (기본: 자동)")
    args = ap.parse_args()

    import torch
    import torchaudio

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    if device == "cpu":
        torch.set_num_threads(max(1, torch.get_num_threads()))

    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    print(f"[dub] device={device}  lang={args.lang}  script={args.script}", flush=True)
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    sr = model.sr

    units = load_units(args.script)
    sentences = []  # (seg_idx, text) — pause는 조립 때 처리
    for kind, payload in units:
        if kind == "text":
            for part in split_long(payload, args.max_chars):
                sentences.append(part)
    n_text = len(sentences)
    print(f"[dub] {n_text}개 문장 합성 예정", flush=True)

    work = args.work or args.out.with_suffix(".segments")
    work.mkdir(parents=True, exist_ok=True)

    # 1) 문장별 합성 (캐시 재사용)
    seg_paths = {}
    done = 0
    si = 0
    for kind, payload in units:
        if kind != "text":
            continue
        for part in split_long(payload, args.max_chars):
            seg = work / seg_name(si, part, args.lang, args.ref)
            if not seg.exists():
                last_err = None
                for attempt in range(1, args.retries + 1):
                    try:
                        torch.manual_seed(args.seed + si * 7 + attempt)
                        wav = model.generate(
                            part,
                            language_id=args.lang,
                            audio_prompt_path=str(args.ref),
                            exaggeration=args.exaggeration,
                            cfg_weight=args.cfg_weight,
                        )
                        torchaudio.save(str(seg), wav.cpu(), sr)
                        last_err = None
                        break
                    except Exception as e:  # noqa: BLE001 — 재시도 후 아래서 보고
                        last_err = e
                        print(f"[dub] 문장 {si} 시도 {attempt} 실패: {e}", flush=True)
                if last_err is not None:
                    print(f"[dub] 중단: 문장 {si} 합성 실패 — {part[:60]}...", file=sys.stderr)
                    return 1
            seg_paths[si] = seg
            si += 1
            done += 1
            if done % 10 == 0 or done == n_text:
                print(f"[dub] {done}/{n_text} 완료", flush=True)

    # 2) 쉼을 넣어 조립
    pieces = []
    pause = torch.zeros(1, int(sr * args.pause))
    para = torch.zeros(1, int(sr * args.paragraph_pause))
    si = 0
    first = True
    for kind, payload in units:
        if kind == "pause":
            if pieces:
                pieces.append(para)
            continue
        for _ in split_long(payload, args.max_chars):
            if not first:
                pieces.append(pause)
            wav, seg_sr = torchaudio.load(str(seg_paths[si]))
            assert seg_sr == sr
            pieces.append(wav)
            first = False
            si += 1

    full = torch.cat(pieces, dim=1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raw = args.out.with_suffix(".raw.wav")
    torchaudio.save(str(raw), full, sr)

    # 3) 음량 정규화 (ffmpeg 없으면 raw를 그대로 출력 이름으로)
    if loudnorm(raw, args.out):
        raw.unlink()
    else:
        raw.rename(args.out if args.out.suffix == ".wav" else args.out.with_suffix(".wav"))
        print("[dub] ffmpeg 없음 — 음량 정규화 생략", flush=True)

    dur = full.shape[1] / sr
    print(f"[dub] 완료: {args.out}  ({dur/60:.1f}분)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
