"""Assemble the trailer frames into an MP4 with fading Korean captions (ffmpeg drawtext)."""
import os, subprocess, sys
S = sys.argv[1]
OUT = sys.argv[2]
FONT_B = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
# (start, end, text, size, y, font)
T = 65.0                  # length of the trailer (s) = frames / 30
CAPS = [
    (0.6, 6.6, '신촌 캠퍼스 1997', 104, 'h*0.70', FONT_B),
    (1.2, 6.6, '1997년 5월, 연세대학교 신촌캠퍼스', 44, 'h*0.70+130', FONT),
    (7.6, 12.6, '하늘에서 둘러보는 그때의 캠퍼스', 54, 'h*0.82', FONT),
    (13.6, 19.0, '은행나무 가로수와 현수막이 걸린 1997년의 백양로', 50, 'h*0.82', FONT),
    (25.5, 31.0, '그리고, 그 시절 백양로를 걸어 봅니다', 54, 'h*0.82', FONT),
    (34.0, 38.8, '다시 하늘로, 가고 싶은 곳으로 한 번에', 54, 'h*0.82', FONT),
    (40.8, 46.6, '독수리상', 84, 'h*0.74', FONT_B),
    (41.3, 46.6, '1970년, 학생들의 모금으로 세운 연세의 상징', 44, 'h*0.74+105', FONT),
    (54.4, 59.4, '언더우드 동상', 84, 'h*0.74', FONT_B),
    (54.9, 59.4, '언더우드관 앞 정원 입구에서 두 팔 벌려 맞이하는', 44, 'h*0.74+105', FONT),
    (59.9, T, '신촌 캠퍼스 1997', 84, 'h*0.70', FONT_B),
    (60.4, T, 'yonsei-alumni.github.io/campus-1997', 46, 'h*0.70+110', FONT),
]

def esc(t):
    return t.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'").replace(',', '\\,')

parts = []
for a, b, text, size, y, font in CAPS:
    alpha = f"if(lt(t\\,{a})\\,0\\,if(lt(t\\,{a + 0.6})\\,(t-{a})/0.6\\,if(lt(t\\,{b - 0.6})\\,1\\,if(lt(t\\,{b})\\,({b}-t)/0.6\\,0))))"
    parts.append(f"drawtext=fontfile={font}:text='{esc(text)}':fontsize={size}:fontcolor=white:x=(w-text_w)/2:y={y}"
                 f":shadowcolor=black@0.6:shadowx=3:shadowy=3:alpha='{alpha}':enable='between(t\\,{a}\\,{b})'")
vf = ','.join(parts) + f',fade=t=in:st=0:d=0.8,fade=t=out:st={T - 1.0}:d=1.0,format=yuv420p'
cmd = ['ffmpeg', '-y', '-framerate', '30', '-i', os.path.join(S, 'frames', '%05d.jpg'),
       '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',
       '-vf', vf, '-c:v', 'libx264', '-preset', 'slow', '-crf', '21', '-maxrate', '14M', '-bufsize', '28M', '-profile:v', 'high', '-r', '30',
       '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', OUT]
print(' '.join(cmd[:8]), '...')
subprocess.run(cmd, check=True)
