#!/usr/bin/env bash
# Create a runnable macOS app bundle layout (requires PySide6 installed).
# Usage: ./scripts/macos_app.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${ROOT}/dist/LiteVNA Studio.app"
CONTENTS="${APP}/Contents"
MACOS="${CONTENTS}/MacOS"
RES="${CONTENTS}/Resources"

rm -rf "${APP}"
mkdir -p "${MACOS}" "${RES}"

cat > "${CONTENTS}/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>LiteVNA Studio</string>
  <key>CFBundleDisplayName</key><string>LiteVNA Studio</string>
  <key>CFBundleIdentifier</key><string>com.litevna.studio</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundleExecutable</key><string>LiteVNA Studio</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSBluetoothAlwaysUsageDescription</key>
  <string>LiteVNA Studio may access serial/USB devices.</string>
</dict>
</plist>
PLIST

cat > "${MACOS}/LiteVNA Studio" <<EOF
#!/bin/bash
DIR="\$(cd "\$(dirname "\$0")" && pwd)"
ROOT="\$(cd "\$DIR/../../.." && pwd)"
# When bundled next to repo:
if [[ -d "\$ROOT/src/litevna" ]]; then
  export PYTHONPATH="\$ROOT/src"
  cd "\$ROOT"
else
  # Installed layout: Resources holds venv hint
  export PYTHONPATH="\$DIR/../Resources/src:\${PYTHONPATH:-}"
fi
if command -v python3 >/dev/null; then
  exec python3 -m litevna.app
fi
exec python -m litevna.app
EOF
chmod +x "${MACOS}/LiteVNA Studio"

# Copy sources into Resources for standalone-ish layout
mkdir -p "${RES}/src"
cp -R "${ROOT}/src/litevna" "${RES}/src/"

echo "Created: ${APP}"
echo "On macOS: open \"${APP}\""
echo "Or run: PYTHONPATH=src python3 -m litevna.app"
