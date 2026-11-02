#!/bin/bash
# 造世界｜主世界地图 一键安装（macOS）
# 作用：把工程复制进编辑器目录，并在 projects.json 里登记

cd "$(dirname "$0")" || exit 1
set -u

APP_DIR="$HOME/Library/Application Support/AI World Creator"
DEST="$APP_DIR/projects"
NAME="project_vqo1bvzh"
SRC="$PWD/projects/$NAME"
STAMP="$(date +%Y%m%d%H%M%S)"

echo "======================================"
echo "  造世界｜主世界地图 安装程序（macOS）"
echo "======================================"
echo

if [ ! -d "$SRC" ]; then
  echo "❌ 找不到工程文件夹：$SRC"
  echo "   请把整个压缩包解压后再运行本脚本。"
  read -n 1 -s -r -p "按任意键退出..."
  exit 1
fi

if [ ! -d "$APP_DIR" ]; then
  echo "⚠️  没找到造世界编辑器的数据目录："
  echo "   $APP_DIR"
  echo "   请先打开一次造世界编辑器并登录，退出后再运行本脚本。"
  read -n 1 -s -r -p "按任意键退出..."
  exit 1
fi

mkdir -p "$DEST" || exit 1

if [ -d "$DEST/$NAME" ]; then
  mv "$DEST/$NAME" "$DEST/$NAME.bak-$STAMP"
  echo "ℹ️  已存在的同名工程已备份为：$NAME.bak-$STAMP"
fi

cp -R "$SRC" "$DEST/$NAME" || { echo "❌ 复制工程失败"; read -n 1 -s -r -p "按任意键退出..."; exit 1; }
echo "✅ 工程已复制到：$DEST/$NAME"

if [ -f "$DEST/projects.json" ]; then
  cp "$DEST/projects.json" "$DEST/projects.json.bak-$STAMP"
  echo "ℹ️  已备份原 projects.json"
fi

RESULT="$(osascript -l JavaScript "$PWD/tools/update-projects.js" "$DEST" "$NAME" 2>&1)"
if [ "$RESULT" != "ok" ]; then
  echo "❌ 登记到 projects.json 失败：$RESULT"
  echo "   你可以手动安装：把 projects.json 里加一项，projectPath 指向"
  echo "   $DEST/$NAME"
  read -n 1 -s -r -p "按任意键退出..."
  exit 1
fi

echo "✅ 已在 projects.json 里登记"
echo
echo "🎉 安装完成！"
echo "   现在重新打开造世界编辑器，在项目列表里点「糖果童趣小镇（主世界）」即可。"
echo
read -n 1 -s -r -p "按任意键关闭这个窗口..."
