# anypc — control the systemd user services from any directory.
#
# This file is meant to be *sourced*, not executed:
#   source /opt/anypc/scripts/anypc.sh
#   anypc launch
#
# `make install` adds a line to ~/.bashrc that sources this automatically, so
# the `anypc` command is available in interactive shells.

anypc() {
  local services="anypc-vnc.service anypc-server.service"
  case "$1" in
    launch|start)
      systemctl --user daemon-reload
      systemctl --user start $services ;;
    stop)
      systemctl --user stop $services ;;
    restart)
      systemctl --user restart $services ;;
    status)
      systemctl --user --no-pager status $services ;;
    logs)
      journalctl --user -u anypc-vnc -u anypc-server -n 80 --no-pager "${@:2}" ;;
    *)
      echo "usage: anypc {launch|stop|restart|status|logs}" >&2
      return 1 ;;
  esac
}
