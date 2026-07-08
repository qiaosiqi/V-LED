/*
 * B part: UDP bridge from /dev/vled to Windows VLED simulator.
 *
 * /dev/vled protocol:
 *   write: text commands, for example:
 *          TEXT Hello VLED
 *          COLOR 255 0 0
 *          BRIGHTNESS 80
 *          MODE scroll
 *          CLEAR
 *          STATUS
 *
 *   read:  one-line JSON string, for example:
 *          {"type":"state","width":32,"height":16,"text":"Hello VLED",
 *           "color":[255,0,0],"brightness":80,"mode":"static","version":12}
 *
 * Build:
 *   gcc -Wall -Wextra -O2 -o vled_bridge vled_bridge.c
 *
 * Example:
 *   ./vled_bridge 192.168.1.10
 *   ./vled_bridge 192.168.1.10 9000 /dev/vled 500
 */

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#define DEFAULT_DEV "/dev/vled"
#define DEFAULT_PORT 9000
#define DEFAULT_INTERVAL_MS 500
#define BUF_SIZE 4096

static volatile sig_atomic_t running = 1;

static void on_signal(int signo)
{
    (void)signo;
    running = 0;
}

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage:\n"
            "  %s <windows_ip> [udp_port] [device] [interval_ms]\n",
            prog);
}

static int parse_port(const char *text)
{
    char *end = NULL;
    unsigned long port = strtoul(text, &end, 10);
    if (end == text || *end != '\0' || port == 0 || port > 65535) {
        return -1;
    }
    return (int)port;
}

static unsigned int parse_interval_ms(const char *text)
{
    char *end = NULL;
    unsigned long value = strtoul(text, &end, 10);
    if (end == text || *end != '\0' || value == 0) {
        return DEFAULT_INTERVAL_MS;
    }
    return (unsigned int)value;
}

static int open_udp_socket(const char *ip, int port, struct sockaddr_in *addr)
{
    int sock = socket(AF_INET, SOCK_DGRAM, 0);

    if (sock < 0) {
        perror("socket");
        return -1;
    }

    memset(addr, 0, sizeof(*addr));
    addr->sin_family = AF_INET;
    addr->sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, ip, &addr->sin_addr) != 1) {
        fprintf(stderr, "invalid ip: %s\n", ip);
        close(sock);
        return -1;
    }

    return sock;
}

static ssize_t read_vled_once(const char *dev, char *buf, size_t size)
{
    int fd = open(dev, O_RDONLY);
    ssize_t n;

    if (fd < 0) {
        perror("open /dev/vled");
        return -1;
    }

    n = read(fd, buf, size - 1);
    if (n < 0) {
        perror("read /dev/vled");
        close(fd);
        return -1;
    }

    buf[n] = '\0';
    close(fd);
    return n;
}

static int looks_like_state_json(const char *payload)
{
    return strchr(payload, '{') != NULL &&
           strstr(payload, "\"type\"") != NULL &&
           strstr(payload, "\"state\"") != NULL;
}

int main(int argc, char **argv)
{
    const char *ip;
    const char *dev = DEFAULT_DEV;
    int port = DEFAULT_PORT;
    int sock;
    struct sockaddr_in udp_addr;
    unsigned int interval_ms = DEFAULT_INTERVAL_MS;
    char buf[BUF_SIZE + 1];

    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    ip = argv[1];
    if (argc >= 3) {
        port = parse_port(argv[2]);
        if (port < 0) {
            fprintf(stderr, "invalid port: %s\n", argv[2]);
            return 1;
        }
    }
    if (argc >= 4) {
        dev = argv[3];
    }
    if (argc >= 5) {
        interval_ms = parse_interval_ms(argv[4]);
    }

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);

    sock = open_udp_socket(ip, port, &udp_addr);
    if (sock < 0) {
        return 1;
    }

    printf("UDP bridge started: %s -> %s:%d, interval=%u ms\n",
           dev, ip, port, interval_ms);

    while (running) {
        ssize_t n = read_vled_once(dev, buf, sizeof(buf));
        if (n > 0) {
            if (!looks_like_state_json(buf)) {
                fprintf(stderr, "skip non-state payload: %s\n", buf);
            } else if (sendto(sock, buf, (size_t)n, 0,
                              (const struct sockaddr *)&udp_addr,
                              sizeof(udp_addr)) < 0) {
                perror("sendto");
                close(sock);
                return 1;
            } else {
                printf("sent %zd bytes: %s\n", n, buf);
            }
        }
        usleep(interval_ms * 1000U);
    }

    close(sock);
    puts("UDP bridge stopped");
    return 0;
}
