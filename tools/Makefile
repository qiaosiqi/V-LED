CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2

.PHONY: all clean

all: vled_cli vled_bridge vled_fd_probe

vled_cli: vled_cli.c
	$(CC) $(CFLAGS) -o $@ $<

vled_bridge: vled_bridge.c
	$(CC) $(CFLAGS) -o $@ $<

vled_fd_probe: vled_fd_probe.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f vled_cli vled_bridge vled_fd_probe
