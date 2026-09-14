# docs/demo.tape — 用 vhs 录制首屏 GIF（可选路线，需 vhs）
#
# 安装：brew install vhs   （依赖 ffmpeg / ttyd）
# 录制：vhs docs/demo.tape
#
# 本仓库另有一条无外部二进制依赖的路线：python3 scripts/make_gif.py（Pillow）。
# 两条路线都消费 scripts/make_demo.py 的真实输出，不是摆拍。
Output docs/demo.gif
Set Shell "bash"
Set FontSize 20
Set Width 900
Set Height 440
Set Padding 16
Set Theme "Dracula"
Type "python3 scripts/make_demo.py"
Enter
Sleep 5s
