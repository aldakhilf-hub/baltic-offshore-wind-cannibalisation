#!/bin/zsh
# usage: export_pdf.sh <in.pptx> <out.pdf>   (PowerPoint via AppleScript; output must be a POSIX file object)
IN="$1"; OUTP="$2"; rm -f "$OUTP"
osascript <<APPLESCRIPT
tell application "Microsoft PowerPoint"
  open (POSIX file "$IN")
  delay 1
  set pres to active presentation
  save pres in (POSIX file "$OUTP") as save as PDF
  delay 2
  close pres saving no
end tell
APPLESCRIPT
sleep 2; [ -f "$OUTP" ] && echo "PDF ok: $OUTP" || echo "PDF FAILED"
