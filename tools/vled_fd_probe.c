/*
 * P1 acceptance probe for PAGE_SIZE buffering and per-open file context.
 * Run against a freshly loaded vled module.
 */

#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifdef _WIN32
#include <windows.h>
#ifndef O_NONBLOCK
#define O_NONBLOCK 0
#endif
#endif

#define DEFAULT_DEV "/dev/vled"
#define STATE_CAPACITY 8192

static int failures;

static int verbose_enabled(void)
{
    const char *value = getenv("VLED_VERBOSE");

    return value && value[0] != '\0' && strcmp(value, "0") != 0;
}

static void detail(const char *format, ...)
{
    va_list args;

    if (!verbose_enabled())
        return;
    fputs("  [DETAIL] ", stdout);
    va_start(args, format);
    vprintf(format, args);
    va_end(args);
    putchar('\n');
}

static long system_page_size(void)
{
#ifdef _WIN32
    SYSTEM_INFO info;

    GetSystemInfo(&info);
    return (long)info.dwPageSize;
#else
    return sysconf(_SC_PAGESIZE);
#endif
}

static void pass(const char *id)
{
    printf("PASS %-12s\n", id);
}

static void fail(const char *id, const char *message)
{
    fprintf(stderr, "FAIL %-12s %s\n", id, message);
    failures++;
}

static int open_checked(const char *id, const char *dev, int flags)
{
    int fd = open(dev, flags);

    if (fd < 0) {
        char message[256];

        snprintf(message, sizeof(message), "open(%s): %s", dev,
                 strerror(errno));
        fail(id, message);
    } else {
        detail("%s open(%s, flags=0x%x) -> fd=%d; new open starts with "
               "independent offsets", id, dev, flags, fd);
    }
    return fd;
}

static int write_exact(const char *id, int fd, const void *data, size_t size)
{
    ssize_t written = write(fd, data, size);

    if (written != (ssize_t)size) {
        char message[256];

        if (written < 0) {
            snprintf(message, sizeof(message), "write(%zu): %s", size,
                     strerror(errno));
        } else {
            snprintf(message, sizeof(message),
                     "short write: expected %zu, got %zd", size, written);
        }
        fail(id, message);
        return -1;
    }
    detail("%s write(fd=%d, count=%zu) -> %zd", id, fd, size, written);
    return 0;
}

static int expect_write_error(const char *id, int fd, const void *data,
                              size_t size, int expected_errno)
{
    ssize_t written;

    errno = 0;
    written = write(fd, data, size);
    if (written != -1 || errno != expected_errno) {
        char message[256];

        snprintf(message, sizeof(message),
                 "expected -1/%s, got %zd/%s", strerror(expected_errno),
                 written, strerror(errno));
        fail(id, message);
        return -1;
    }
    detail("%s write(fd=%d, count=%zu) -> -1/%s as expected", id, fd,
           size, strerror(expected_errno));
    return 0;
}

static int read_all_fd(const char *id, int fd, char *output, size_t capacity,
                       size_t chunk_size)
{
    size_t used = 0;

    while (used + 1 < capacity) {
        size_t request = chunk_size;
        ssize_t count;

        if (request > capacity - used - 1)
            request = capacity - used - 1;
        count = read(fd, output + used, request);
        if (count < 0) {
            if (errno == EAGAIN)
                break;
            char message[256];

            snprintf(message, sizeof(message), "read: %s", strerror(errno));
            fail(id, message);
            return -1;
        }
        if (count == 0)
            break;
        used += (size_t)count;
    }

    if (used + 1 == capacity) {
        fail(id, "state exceeded probe buffer");
        return -1;
    }
    output[used] = '\0';
    return (int)used;
}

static int read_exact_fd(const char *id, int fd, char *output, size_t size,
                         size_t chunk_size)
{
    size_t used = 0;

    while (used < size) {
        size_t request = chunk_size < size - used ? chunk_size : size - used;
        ssize_t count = read(fd, output + used, request);

        if (count <= 0) {
            char message[256];

            if (count < 0)
                snprintf(message, sizeof(message), "read: %s", strerror(errno));
            else
                snprintf(message, sizeof(message),
                         "early EOF: expected %zu more bytes", size - used);
            fail(id, message);
            return -1;
        }
        used += (size_t)count;
    }
    return (int)used;
}

static int read_state(const char *id, const char *dev, char *output)
{
    int fd = open_checked(id, dev, O_RDONLY | O_NONBLOCK);
    int size;

    if (fd < 0)
        return -1;
    size = read_all_fd(id, fd, output, STATE_CAPACITY, 127);
    close(fd);
    return size;
}

static int write_command(const char *id, const char *dev, const char *command)
{
    int fd = open_checked(id, dev, O_WRONLY);
    int result;

    if (fd < 0)
        return -1;
    result = write_exact(id, fd, command, strlen(command));
    close(fd);
    return result;
}

static long parse_version(const char *json)
{
    const char *field = strstr(json, "\"version\":");
    char *end;
    unsigned long value;

    if (!field)
        return -1;
    field += strlen("\"version\":");
    errno = 0;
    value = strtoul(field, &end, 10);
    if (errno || end == field || (*end != '}' && *end != ','))
        return -1;
    return (long)value;
}

static int looks_like_state(const char *json)
{
    size_t size = strlen(json);

    return size > 2 && json[0] == '{' && json[size - 1] == '}' &&
           strstr(json, "\"type\":\"state\"") &&
           strstr(json, "\"width\":") && strstr(json, "\"height\":") &&
           strstr(json, "\"text\":") && strstr(json, "\"color\":[") &&
           strstr(json, "\"brightness\":") && strstr(json, "\"mode\":") &&
           parse_version(json) >= 0;
}

static void test_default_and_versions(const char *dev)
{
    char before[STATE_CAPACITY];
    char changed[STATE_CAPACITY];
    char repeated[STATE_CAPACITY];
    long initial_version;
    long changed_version;

    if (read_state("T-BUF-01", dev, before) < 0)
        return;
    initial_version = parse_version(before);
    if (!looks_like_state(before) || initial_version != 0) {
        fail("T-BUF-01", "fresh module did not expose valid version 0 JSON");
        return;
    }
    pass("T-BUF-01");

    if (write_command("T-VERSION", dev, "TEXT p1-version") < 0 ||
        read_state("T-VERSION", dev, changed) < 0)
        return;
    changed_version = parse_version(changed);
    if (changed_version != initial_version + 1) {
        fail("T-VERSION", "actual state change did not increment once");
        return;
    }
    if (write_command("T-VERSION", dev, "TEXT p1-version") < 0 ||
        read_state("T-VERSION", dev, repeated) < 0)
        return;
    if (strcmp(changed, repeated) != 0) {
        fail("T-VERSION", "repeated value changed JSON or version");
        return;
    }
    pass("T-VERSION");
}

static void test_boundaries_and_independent_writes(const char *dev,
                                                   size_t page_size)
{
    char before[STATE_CAPACITY];
    char after[STATE_CAPACITY];
    char *page = calloc(page_size + 1, 1);
    int fd_a;
    int fd_b;
    int ok = 1;

    if (!page) {
        fail("T-BUF-02..06", "allocation failed");
        return;
    }
    memset(page, ' ', page_size + 1);
    memcpy(page, "STATUS", strlen("STATUS"));
    detail("PAGE_SIZE=%zu: legal per-open capacity is PAGE_SIZE-1=%zu bytes",
           page_size, page_size - 1);

    fd_a = open_checked("T-FOPS-05", dev, O_RDWR);
    if (fd_a < 0) {
        free(page);
        return;
    }
    if (write(fd_a, page, 0) != 0) {
        fail("T-FOPS-05", "zero-length write did not return 0");
        ok = 0;
    } else {
        char byte;
        if (read(fd_a, &byte, 0) != 0) {
            fail("T-FOPS-05", "zero-length read did not return 0");
            ok = 0;
        }
    }
    if (ok)
        pass("T-FOPS-05");
    close(fd_a);

    if (read_state("T-BUF-03..04", dev, before) < 0) {
        free(page);
        return;
    }
    fd_a = open_checked("T-BUF-03", dev, O_WRONLY);
    if (fd_a >= 0) {
        if (expect_write_error("T-BUF-03", fd_a, page, page_size,
                               EMSGSIZE) == 0)
            pass("T-BUF-03");
        close(fd_a);
    }
    fd_a = open_checked("T-BUF-04", dev, O_WRONLY);
    if (fd_a >= 0) {
        if (expect_write_error("T-BUF-04", fd_a, page, page_size + 1,
                               EMSGSIZE) == 0)
            pass("T-BUF-04");
        close(fd_a);
    }
    if (read_state("T-BUF-03..04", dev, after) >= 0 &&
        strcmp(before, after) != 0)
        fail("T-BUF-03..04", "oversize write changed shared state");

    fd_a = open_checked("T-BUF-02", dev, O_WRONLY);
    fd_b = open_checked("T-BUF-06", dev, O_WRONLY);
    if (fd_a >= 0 && fd_b >= 0) {
        detail("T-BUF-02/T-BUF-06 fd_a=%d and fd_b=%d are separate opens",
               fd_a, fd_b);
        if (write_exact("T-BUF-02", fd_a, page, page_size - 1) == 0)
            pass("T-BUF-02");
        if (expect_write_error("T-BUF-05", fd_a, "X", 1, ENOSPC) == 0)
            pass("T-BUF-05");
        if (write_exact("T-BUF-06", fd_b, "STATUS", strlen("STATUS")) == 0)
            pass("T-BUF-06");
        detail("fd_a remained full while fd_b wrote from its own offset 0");
    }
    if (fd_a >= 0)
        close(fd_a);
    if (fd_b >= 0)
        close(fd_b);
    free(page);
}

static void test_nonseekable(const char *dev)
{
    int fd = open_checked("T-FOPS-04", dev, O_RDONLY);

    if (fd < 0)
        return;
    errno = 0;
    if (lseek(fd, 0, SEEK_SET) != (off_t)-1 || errno != ESPIPE) {
        fail("T-FOPS-04", "lseek did not fail with ESPIPE");
    } else {
        pass("T-FOPS-04");
    }
    close(fd);
}

static void test_atomic_rollback(const char *dev, size_t page_size)
{
    char before[STATE_CAPACITY];
    char after[STATE_CAPACITY];
    char consumed[STATE_CAPACITY];
    char *page = calloc(page_size, 1);
    char byte;
    int fd;
    int ok = 1;

    if (!page) {
        fail("T-ROLLBACK", "allocation failed");
        return;
    }
    memset(page, ' ', page_size);
    memcpy(page, "STATUS", strlen("STATUS"));

    if (read_state("T-ROLLBACK", dev, before) < 0) {
        free(page);
        return;
    }
    fd = open_checked("T-ROLLBACK", dev, O_RDWR | O_NONBLOCK);
    if (fd < 0) {
        free(page);
        return;
    }
    if (expect_write_error("T-ROLLBACK", fd, "COLOR 256 0 0",
                           strlen("COLOR 256 0 0"), EINVAL) < 0)
        ok = 0;
    if (write_exact("T-ROLLBACK", fd, page, page_size - 1) < 0)
        ok = 0;
    close(fd);
    if (read_state("T-ROLLBACK", dev, after) < 0 || strcmp(before, after) != 0) {
        fail("T-ROLLBACK", "failed command changed state/version or consumed capacity");
        ok = 0;
    }

    /* P5 blocks at an exhausted snapshot; use nonblocking mode so this
     * rollback check can assert EAGAIN instead of waiting for a new version. */
    fd = open_checked("T-ROLLBACK", dev, O_RDWR | O_NONBLOCK);
    if (fd >= 0) {
        if (read_all_fd("T-ROLLBACK", fd, consumed, sizeof(consumed), 31) < 0)
            ok = 0;
        if (expect_write_error("T-ROLLBACK", fd, "MODE blink",
                               strlen("MODE blink"), EINVAL) < 0)
            ok = 0;
        errno = 0;
        if (read(fd, &byte, 1) != -1 || errno != EAGAIN) {
            fail("T-ROLLBACK", "failed write refreshed or rewound read snapshot");
            ok = 0;
        }
        close(fd);
    } else {
        ok = 0;
    }
    if (ok)
        pass("T-ROLLBACK");
    free(page);
}

static void test_multifd_snapshot(const char *dev)
{
    char old_state[STATE_CAPACITY];
    char reconstructed[STATE_CAPACITY];
    char new_state[STATE_CAPACITY];
    char prefix_a[23];
    char prefix_b[23];
    ssize_t first_a;
    ssize_t first_b;
    int fd_a;
    int fd_b;
    int rest;
    size_t expected_rest;
    int ok = 1;

    if (write_command("T-FD-03", dev, "TEXT snapshot-old") < 0 ||
        read_state("T-FD-03", dev, old_state) < 0)
        return;

    fd_a = open_checked("T-FD-01", dev, O_RDONLY | O_NONBLOCK);
    fd_b = open_checked("T-FD-01", dev, O_RDONLY | O_NONBLOCK);
    if (fd_a < 0 || fd_b < 0) {
        if (fd_a >= 0)
            close(fd_a);
        if (fd_b >= 0)
            close(fd_b);
        return;
    }
    first_a = read(fd_a, prefix_a, sizeof(prefix_a));
    first_b = read(fd_b, prefix_b, sizeof(prefix_b));
    detail("T-FD-01 fd_a=%d read %zd bytes and fd_b=%d read %zd bytes; "
           "both reads began at offset 0", fd_a, first_a, fd_b, first_b);
    if (first_a != (ssize_t)sizeof(prefix_a) || first_b != first_a ||
        memcmp(prefix_a, prefix_b, (size_t)first_a) != 0) {
        fail("T-FD-01", "independent opens did not start at read offset 0");
        close(fd_b);
        close(fd_a);
        return;
    } else {
        pass("T-FD-01");
    }
    close(fd_b);

    memcpy(reconstructed, prefix_a, (size_t)first_a);
    if (write_command("T-FD-03", dev, "TEXT snapshot-new") < 0)
        ok = 0;
    expected_rest = strlen(old_state) - (size_t)first_a;
    rest = read_exact_fd("T-FD-03", fd_a, reconstructed + first_a,
                         expected_rest, 7);
    close(fd_a);
    if (rest >= 0) {
        reconstructed[first_a + rest] = '\0';
        if (strcmp(reconstructed, old_state) != 0) {
            fail("T-FD-03", "reader mixed old and new snapshots");
            ok = 0;
        }
    } else {
        ok = 0;
    }
    if (read_state("T-READ-03", dev, new_state) < 0 ||
        !strstr(new_state, "\"text\":\"snapshot-new\"") ||
        strcmp(new_state, old_state) == 0) {
        fail("T-READ-03", "new open did not observe latest state");
        ok = 0;
    } else {
        pass("T-READ-03");
    }
    if (ok)
        pass("T-FD-03");
}

static void test_dup_offset(const char *dev)
{
    char expected[STATE_CAPACITY];
    char combined[STATE_CAPACITY];
    ssize_t first;
    int fd;
    int duplicate;
    int rest;

    if (read_state("T-FD-04", dev, expected) < 0)
        return;
    fd = open_checked("T-FD-04", dev, O_RDONLY | O_NONBLOCK);
    if (fd < 0)
        return;
    duplicate = dup(fd);
    if (duplicate < 0) {
        fail("T-FD-04", "dup failed");
        close(fd);
        return;
    }
    first = read(fd, combined, 11);
    detail("T-FD-04 original fd=%d read first %zd bytes; dup fd=%d must "
           "continue the shared open-file offset", fd, first, duplicate);
    if (first != 11) {
        fail("T-FD-04", "first dup read was short");
        close(duplicate);
        close(fd);
        return;
    }
    rest = read_all_fd("T-FD-04", duplicate, combined + first,
                       sizeof(combined) - (size_t)first, 19);
    close(duplicate);
    close(fd);
    if (rest < 0)
        return;
    combined[first + rest] = '\0';
    if (strcmp(combined, expected) != 0) {
        fail("T-FD-04", "dup descriptors did not share one file offset");
        return;
    }
    pass("T-FD-04");
}

static void test_json_escaping(const char *dev)
{
    const char command[] = "TEXT 中文 \"quote\" \\slash\tend";
    char state[STATE_CAPACITY];

    if (write_command("T-JSON-02..03", dev, command) < 0 ||
        read_state("T-JSON-02..03", dev, state) < 0)
        return;
    if (!looks_like_state(state) || !strstr(state, "中文") ||
        !strstr(state, "\\\"quote\\\"") ||
        !strstr(state, "\\\\slash\\tend")) {
        fail("T-JSON-02..03", "UTF-8 or JSON escaping was not preserved");
        return;
    }
    pass("T-JSON-02..03");
}

int main(int argc, char **argv)
{
    const char *dev = argc > 1 ? argv[1] : DEFAULT_DEV;
    long page_size = system_page_size();

    if (argc > 2) {
        fprintf(stderr, "Usage: %s [device]\n", argv[0]);
        return 2;
    }
    if (page_size <= 0) {
        fprintf(stderr, "Unable to determine PAGE_SIZE\n");
        return 2;
    }

    printf("VLED P1 probe: device=%s page_size=%ld\n", dev, page_size);
    test_default_and_versions(dev);
    test_boundaries_and_independent_writes(dev, (size_t)page_size);
    test_nonseekable(dev);
    test_atomic_rollback(dev, (size_t)page_size);
    test_multifd_snapshot(dev);
    test_dup_offset(dev);
    test_json_escaping(dev);

    if (failures) {
        fprintf(stderr, "VLED P1 probe: %d failure(s)\n", failures);
        return 1;
    }
    puts("VLED P1 probe: all checks passed");
    return 0;
}
