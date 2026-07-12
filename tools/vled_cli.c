/*
 * B part: user-space CLI tester for /dev/vled.
 *
 * Build:
 *   gcc -Wall -Wextra -O2 -o vled_cli vled_cli.c
 *
 * Examples:
 *   ./vled_cli read
 *   ./vled_cli write "TEXT Hello VLED"
 *   ./vled_cli write "COLOR 255 0 0"
 *   ./vled_cli write "BRIGHTNESS 80"
 *   ./vled_cli write "MODE scroll"
 *   ./vled_cli loop 1
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define DEFAULT_DEV "/dev/vled"
#define BUF_SIZE 4096

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage:\n"
            "  %s read [device]\n"
            "  %s write <text> [device]\n"
            "  %s loop [interval_seconds] [device]\n",
            prog, prog, prog);
}

static const char *device_arg(int argc, char **argv, int index)
{
    return argc > index ? argv[index] : DEFAULT_DEV;
}

static int read_device(const char *dev)
{
    char buf[BUF_SIZE + 1];
    int fd = open(dev, O_RDONLY);
    ssize_t n;

    if (fd < 0) {
        perror("open");
        return 1;
    }

    n = read(fd, buf, BUF_SIZE);
    if (n < 0) {
        perror("read");
        close(fd);
        return 1;
    }

    buf[n] = '\0';
    printf("%s", buf);
    if (n == 0 || buf[n - 1] != '\n') {
        putchar('\n');
    }

    close(fd);
    return 0;
}

static int write_device(const char *dev, const char *text)
{
    int fd = open(dev, O_WRONLY);
    size_t len = strlen(text);
    ssize_t n;

    if (fd < 0) {
        perror("open");
        return 1;
    }

    n = write(fd, text, len);
    if (n < 0) {
        perror("write");
        close(fd);
        return 1;
    }

    if ((size_t)n != len) {
        fprintf(stderr, "short write: expected %zu bytes, wrote %zd\n", len, n);
        close(fd);
        return 1;
    }

    printf("wrote %zd bytes to %s\n", n, dev);
    close(fd);
    return 0;
}

static int loop_read_device(const char *dev, unsigned int interval)
{
    for (;;) {
        int rc = read_device(dev);
        if (rc != 0) {
            return rc;
        }
        sleep(interval);
    }
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "read") == 0) {
        if (argc > 3) {
            usage(argv[0]);
            return 1;
        }
        return read_device(device_arg(argc, argv, 2));
    }

    if (strcmp(argv[1], "write") == 0) {
        if (argc < 3 || argc > 4) {
            usage(argv[0]);
            return 1;
        }
        return write_device(device_arg(argc, argv, 3), argv[2]);
    }

    if (strcmp(argv[1], "loop") == 0) {
        unsigned int interval = 1;
        const char *dev = DEFAULT_DEV;

        if (argc > 4) {
            usage(argv[0]);
            return 1;
        }
        if (argc >= 3) {
            char *end = NULL;
            unsigned long parsed = strtoul(argv[2], &end, 10);
            if (end == argv[2] || *end != '\0' || parsed == 0 ||
                parsed > 86400) {
                fprintf(stderr, "invalid interval: %s\n", argv[2]);
                return 1;
            }
            interval = (unsigned int)parsed;
        }
        if (argc >= 4) {
            dev = argv[3];
        }
        return loop_read_device(dev, interval);
    }

    usage(argv[0]);
    return 1;
}
