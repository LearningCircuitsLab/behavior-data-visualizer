# Use it from your computer

The Behavior Explorer runs all the time on the cluster (minibaps2, port
**8055**), for everyone. You do not install anything: you open an SSH tunnel
from your computer and use it in your browser. Setting up a computer takes
two steps, done once.

## 1. Add an `explorer` entry to your SSH configuration

On your computer, add this to `~/.ssh/config`. Fill in the same address, user
and jump host that you use to log in to minibaps2 (copy them from your
existing entry for it):

```text
Host explorer
    HostName <address of minibaps2>
    User <your user on the cluster>
    ProxyJump <your entry for the cluster>
    LocalForward 8055 127.0.0.1:8055
```

`LocalForward` connects port 8055 of your computer to port 8055 of minibaps2,
where the dashboard is. Your other entries may forward other ports (e.g.
8050): that is fine, as long as nothing else uses 8055.

## 2. Add the `explorer` command to your terminal

Add this to `~/.bashrc` (Linux, WSL) or `~/.zshrc` (Mac), then open a new
terminal:

```bash
# Behavior Explorer: opens the tunnel to the shared dashboard and prints its address
explorer() {
    local url="http://localhost:8055"
    if (exec 3<>/dev/tcp/127.0.0.1/8055) 2>/dev/null; then
        echo "The tunnel is already open: $url"
        return 0
    fi
    echo "Behavior Explorer: $url   (status: $url/status)"
    echo "Keep this terminal open; Ctrl+C closes the tunnel."
    ssh -N explorer
}
```

## Every time

```bash
explorer
```

It prints the address and opens the tunnel (it may ask for your password).
Open <http://localhost:8055> in your browser, and keep the terminal open
while you use it: it seems to hang, which is normal. Ctrl+C closes the
tunnel. If a tunnel is already open, `explorer` only prints the address.

Without the shortcut, `ssh -N explorer` does the same.

## Good to know

- Several people can use it at the same time: each browser has its own
  choices (project, mouse, day, zoom, video). A mouse someone opened before
  is fast for everyone (its trials stay in memory until the next night).
- <http://localhost:8055/status> shows the code it runs (the commit), since
  when, and the mice in memory.
- It restarts every night at 4 am (to run the latest code and free memory):
  if you are using it then, reload the page after a few seconds.
- It is only reachable through the cluster and has no password: anyone who
  can log in to the cluster can use it.

## If the page does not load

- **Is the tunnel open?** `explorer` (or `ssh -N explorer`) must be running
  in a terminal.
- **`bind: Address already in use`** when opening the tunnel: something on
  your computer already uses port 8055, usually another `explorer` tunnel
  that is still open. Close it, or just use that one.
- **The tunnel opens but the page does not load:** the dashboard may be
  restarting (a few seconds after an update) or stopped; it is started again
  within 5 minutes. If it does not come back, tell whoever looks after it
  (see [the shared dashboard](shared_dashboard.md)).
