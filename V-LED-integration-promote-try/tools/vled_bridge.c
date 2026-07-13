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
#include <poll.h>
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
#define MAX_DIMENSION 128
#define MAX_LED_CELLS 4096

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

static int parse_interval_ms(const char *text, unsigned int *result)
{
    char *end = NULL;
    unsigned long value = strtoul(text, &end, 10);
    if (end == text || *end != '\0' || value == 0 || value > 3600000UL) {
        return -1;
    }
    *result = (unsigned int)value;
    return 0;
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

static int consume_literal(const char **cursor, const char *literal)
{
    size_t size = strlen(literal);

    if (strncmp(*cursor, literal, size) != 0)
        return 0;
    *cursor += size;
    return 1;
}

static int consume_uint(const char **cursor, unsigned long *value)
{
    char *end = NULL;

    if (**cursor < '0' || **cursor > '9')
        return 0;
    errno = 0;
    *value = strtoul(*cursor, &end, 10);
    if (errno || end == *cursor)
        return 0;
    *cursor = end;
    return 1;
}

static int consume_json_string(const char **cursor)
{
    size_t decoded_bytes = 0;

    while (**cursor && **cursor != '"') {
        unsigned char byte = (unsigned char)**cursor;

        if (byte < 0x20)
            return 0;
        if (byte == '\\') {
            (*cursor)++;
            if (!strchr("\"\\/bfnrt", **cursor))
                return 0;
        }
        (*cursor)++;
        decoded_bytes++;
        if (decoded_bytes > 1023)
            return 0;
    }
    if (**cursor != '"')
        return 0;
    (*cursor)++;
    return 1;
}

/* Validate the exact canonical state shape emitted by the VLED driver. */
static int validate_state_json(const char *payload)
{
    const char *cursor = payload;
    unsigned long width, height, red, green, blue, brightness, version;
    const char *mode;

    if (!consume_literal(&cursor, "{\"type\":\"state\",\"width\":" ) ||
        !consume_uint(&cursor, &width) ||
        !consume_literal(&cursor, ",\"height\":" ) ||
        !consume_uint(&cursor, &height) ||
        !consume_literal(&cursor, ",\"text\":\"" ) ||
        !consume_json_string(&cursor) ||
        !consume_literal(&cursor, ",\"color\":[" ) ||
        !consume_uint(&cursor, &red) || !consume_literal(&cursor, ",") ||
        !consume_uint(&cursor, &green) || !consume_literal(&cursor, ",") ||
        !consume_uint(&cursor, &blue) ||
        !consume_literal(&cursor, "],\"brightness\":" ) ||
        !consume_uint(&cursor, &brightness) ||
        !consume_literal(&cursor, ",\"mode\":\"" ))
        return 0;

    mode = cursor;
    while (*cursor && *cursor != '"')
        cursor++;
    if (*cursor != '"')
        return 0;
    if (!((size_t)(cursor - mode) == 6 && strncmp(mode, "static", 6) == 0) &&
        !((size_t)(cursor - mode) == 6 && strncmp(mode, "scroll", 6) == 0))
        return 0;
    cursor++;
    if (!consume_literal(&cursor, ",\"version\":" ) ||
        !consume_uint(&cursor, &version) || !consume_literal(&cursor, "}"))
        return 0;

    return *cursor == '\0' && width >= 1 && width <= MAX_DIMENSION &&
           height >= 1 && height <= MAX_DIMENSION &&
           width * height <= MAX_LED_CELLS && red <= 255 && green <= 255 &&
           blue <= 255 && brightness <= 100;
}

int main(int argc, char **argv)
{
    const char *ip;
    const char *dev = DEFAULT_DEV;
    int port = DEFAULT_PORT;
    int dev_fd;
    int sock;
    struct sockaddr_in udp_addr;
    unsigned int interval_ms = DEFAULT_INTERVAL_MS;
    char buf[BUF_SIZE + 1];

    if (argc < 2 || argc > 5) {
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
        if (parse_interval_ms(argv[4], &interval_ms) != 0) {
            fprintf(stderr, "invalid interval_ms: %s\n", argv[4]);
            return 1;
        }
    }

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);

    sock = open_udp_socket(ip, port, &udp_addr);
    if (sock < 0) {
        return 1;
    }

    dev_fd = open(dev, O_RDONLY | O_NONBLOCK);
    if (dev_fd < 0) {
        perror("open /dev/vled");
        close(sock);
        return 1;
    }

    printf("UDP bridge started: %s -> %s:%d, poll_timeout=%u ms\n",
           dev, ip, port, interval_ms);

    while (running) {
        struct pollfd item = {.fd = dev_fd, .events = POLLIN | POLLRDNORM};
        int poll_result = poll(&item, 1, (int)interval_ms);
        ssize_t n;

        if (poll_result < 0) {
            if (errno == EINTR && !running)
                break;
            if (errno == EINTR)
                continue;
            perror("poll /dev/vled");
            close(dev_fd);
            close(sock);
            return 1;
        }
        if (poll_result == 0)
            continue;
        if (item.revents & (POLLERR | POLLNVAL)) {
            fprintf(stderr, "poll /dev/vled: revents=0x%x\n", item.revents);
            close(dev_fd);
            close(sock);
            return 1;
        }
        if (!(item.revents & (POLLIN | POLLRDNORM)))
            continue;

        n = read(dev_fd, buf, sizeof(buf) - 1);
        if (n < 0 && errno == EAGAIN)
            continue;
        if (n < 0) {
            if (errno == EINTR && !running)
                break;
            perror("read /dev/vled");
            close(dev_fd);
            close(sock);
            return 1;
        }
        buf[n] = '\0';
        if (n > 0) {
            if (!validate_state_json(buf)) {
                fprintf(stderr, "skip non-state payload: %s\n", buf);
            } else if (sendto(sock, buf, (size_t)n, 0,
                              (const struct sockaddr *)&udp_addr,
                              sizeof(udp_addr)) < 0) {
                perror("sendto");
                close(dev_fd);
                close(sock);
                return 1;
            } else {
                printf("sent %zd bytes: %s\n", n, buf);
            }
        }
    }

    close(dev_fd);
    close(sock);
    puts("UDP bridge stopped");
    return 0;
}
