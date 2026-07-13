/* P5 target-Linux acceptance probe for poll + wait queue semantics. */

#include <stdio.h>

#ifdef _WIN32

int main(void)
{
    puts("vled_poll_probe: target Linux runtime required");
    return 0;
}

#else

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define DEFAULT_DEV "/dev/vled"
#define STATE_CAPACITY 8192
#define STRESS_WRITERS 4
#define STRESS_WRITES 100

static int failures;

static void pass(const char *id)
{
    printf("PASS %-12s\n", id);
}

static void fail(const char *id, const char *message)
{
    fprintf(stderr, "FAIL %-12s %s\n", id, message);
    failures++;
}

static int write_command(const char *dev, const char *command, int expected_errno)
{
    int fd = open(dev, O_WRONLY);
    ssize_t result;
    int saved;

    if (fd < 0)
        return -1;
    errno = 0;
    result = write(fd, command, strlen(command));
    saved = errno;
    close(fd);
    if (expected_errno)
        return result == -1 && saved == expected_errno ? 0 : -1;
    return result == (ssize_t)strlen(command) ? 0 : -1;
}

static int poll_readable(int fd, int timeout_ms, short *revents)
{
    struct pollfd item = {.fd = fd, .events = POLLIN | POLLRDNORM};
    int result;

    do {
        result = poll(&item, 1, timeout_ms);
    } while (result < 0 && errno == EINTR);
    if (revents)
        *revents = item.revents;
    return result;
}

static ssize_t read_state_once(int fd, char *state, size_t capacity)
{
    ssize_t result = read(fd, state, capacity - 1);

    if (result >= 0)
        state[result] = '\0';
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
    return errno || end == field ? -1 : (long)value;
}

static int valid_state(const char *json)
{
    size_t length = strlen(json);

    return length > 2 && json[0] == '{' && json[length - 1] == '}' &&
           strstr(json, "\"type\":\"state\"") && parse_version(json) >= 0;
}

static void test_initial_timeout_change_nonblock(const char *dev)
{
    char initial[STATE_CAPACITY];
    char changed[STATE_CAPACITY];
    char command[96];
    struct timespec now;
    short revents = 0;
    long initial_version;
    int fd = open(dev, O_RDONLY | O_NONBLOCK);
    ssize_t count;

    if (fd < 0) {
        fail("T-POLL-01", strerror(errno));
        return;
    }
    if (poll_readable(fd, 0, &revents) != 1 ||
        !(revents & POLLIN) || !(revents & POLLRDNORM)) {
        fail("T-POLL-01", "new descriptor was not immediately readable");
        close(fd);
        return;
    }
    count = read_state_once(fd, initial, sizeof(initial));
    if (count <= 0 || !valid_state(initial)) {
        fail("T-POLL-01", "initial read was not valid state JSON");
        close(fd);
        return;
    }
    initial_version = parse_version(initial);
    pass("T-POLL-01");

    if (poll_readable(fd, 120, &revents) != 0) {
        fail("T-POLL-02", "consumed version remained readable");
    } else {
        pass("T-POLL-02");
    }

    errno = 0;
    if (read(fd, changed, sizeof(changed)) != -1 || errno != EAGAIN) {
        fail("T-POLL-05", "nonblocking read without a new version was not EAGAIN");
    } else {
        pass("T-POLL-05");
    }

    clock_gettime(CLOCK_MONOTONIC, &now);
    snprintf(command, sizeof(command), "TEXT poll-change-%ld-%ld",
             (long)getpid(), now.tv_nsec);
    if (write_command(dev, command, 0) != 0 ||
        poll_readable(fd, 1000, &revents) != 1 ||
        !(revents & POLLIN) || !(revents & POLLRDNORM)) {
        fail("T-POLL-03", "actual state change did not produce readable event");
        close(fd);
        return;
    }
    count = read_state_once(fd, changed, sizeof(changed));
    if (count <= 0 || !valid_state(changed) ||
        parse_version(changed) != initial_version + 1) {
        fail("T-POLL-03", "event read did not return the next valid version");
    } else {
        pass("T-POLL-03");
    }
    close(fd);
}

static void test_noop_writes(const char *dev)
{
    char current[STATE_CAPACITY];
    char repeated[STATE_CAPACITY];
    const char *text;
    const char *end;
    char command[1200];
    short revents;
    int fd = open(dev, O_RDONLY | O_NONBLOCK);

    if (fd < 0 || read_state_once(fd, current, sizeof(current)) <= 0) {
        fail("T-POLL-04", "could not establish consumed state");
        if (fd >= 0)
            close(fd);
        return;
    }
    text = strstr(current, "\"text\":\"");
    if (!text || !(end = strchr(text + 8, '"'))) {
        fail("T-POLL-04", "could not parse current text");
        close(fd);
        return;
    }
    snprintf(command, sizeof(command), "TEXT %.*s", (int)(end - (text + 8)),
             text + 8);
    if (write_command(dev, "STATUS", 0) != 0 ||
        write_command(dev, command, 0) != 0 ||
        write_command(dev, "COLOR 999 0 0", EINVAL) != 0 ||
        poll_readable(fd, 150, &revents) != 0) {
        fail("T-POLL-04", "STATUS, repeated value or invalid write produced an event");
    } else {
        errno = 0;
        if (read(fd, repeated, sizeof(repeated)) != -1 || errno != EAGAIN)
            fail("T-POLL-04", "no-op wake made a new snapshot readable");
        else
            pass("T-POLL-04");
    }
    close(fd);
}

static void empty_handler(int signo)
{
    (void)signo;
}

static void test_signal_interrupt(const char *dev)
{
    int ready_pipe[2];
    pid_t child;
    char ready;
    int status;

    if (pipe(ready_pipe) != 0) {
        fail("T-POLL-06", "pipe failed");
        return;
    }
    child = fork();
    if (child == 0) {
        struct sigaction action = {0};
        char state[STATE_CAPACITY];
        int fd;
        ssize_t result;
        int saved_errno;

        close(ready_pipe[0]);
        action.sa_handler = empty_handler;
        sigemptyset(&action.sa_mask);
        sigaction(SIGUSR1, &action, NULL);
        fd = open(dev, O_RDONLY);
        if (fd < 0 || read_state_once(fd, state, sizeof(state)) <= 0)
            _exit(20);
        if (write(ready_pipe[1], "R", 1) != 1)
            _exit(21);
        errno = 0;
        result = read(fd, state, sizeof(state));
        saved_errno = errno;
        close(fd);
        _exit(result == -1 && saved_errno == EINTR ? 0 : 22);
    }
    close(ready_pipe[1]);
    if (child < 0 || read(ready_pipe[0], &ready, 1) != 1) {
        fail("T-POLL-06", "child did not enter blocking read");
        close(ready_pipe[0]);
        return;
    }
    close(ready_pipe[0]);
    usleep(50000);
    kill(child, SIGUSR1);
    waitpid(child, &status, 0);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
        fail("T-POLL-06", "signal did not interrupt blocking read cleanly");
    else
        pass("T-POLL-06");
}

struct stress_args {
    const char *dev;
    int writer;
    int error;
};

static void *stress_writer(void *opaque)
{
    struct stress_args *args = opaque;
    char command[96];
    int index;

    for (index = 0; index < STRESS_WRITES; index++) {
        snprintf(command, sizeof(command), "TEXT stress-%d-%d",
                 args->writer, index);
        if (write_command(args->dev, command, 0) != 0) {
            args->error = 1;
            break;
        }
    }
    return NULL;
}

static void test_high_frequency_final_state(const char *dev)
{
    pthread_t threads[STRESS_WRITERS];
    struct stress_args args[STRESS_WRITERS];
    char state[STATE_CAPACITY];
    char final_command[96];
    short revents;
    int fd = open(dev, O_RDONLY | O_NONBLOCK);
    int index;
    int created = 0;
    int ok = 1;

    if (fd < 0 || read_state_once(fd, state, sizeof(state)) <= 0) {
        fail("T-POLL-07", "could not consume initial stress state");
        if (fd >= 0)
            close(fd);
        return;
    }
    for (index = 0; index < STRESS_WRITERS; index++) {
        args[index] = (struct stress_args){.dev = dev, .writer = index};
        if (pthread_create(&threads[index], NULL, stress_writer, &args[index])) {
            ok = 0;
            break;
        }
        created++;
    }
    for (index = 0; index < created; index++) {
        pthread_join(threads[index], NULL);
        if (args[index].error)
            ok = 0;
    }
    snprintf(final_command, sizeof(final_command), "TEXT poll-final-%ld", (long)getpid());
    if (write_command(dev, final_command, 0) != 0 ||
        poll_readable(fd, 1000, &revents) != 1 ||
        read_state_once(fd, state, sizeof(state)) <= 0 || !valid_state(state) ||
        !strstr(state, final_command + 5))
        ok = 0;
    if (ok)
        pass("T-POLL-07");
    else
        fail("T-POLL-07", "stress did not converge to valid final state");
    close(fd);
}

int main(int argc, char **argv)
{
    const char *dev = argc > 1 ? argv[1] : DEFAULT_DEV;

    if (argc > 2) {
        fprintf(stderr, "Usage: %s [device]\n", argv[0]);
        return 2;
    }
    test_initial_timeout_change_nonblock(dev);
    test_noop_writes(dev);
    test_signal_interrupt(dev);
    test_high_frequency_final_state(dev);
    if (failures) {
        fprintf(stderr, "VLED P5 probe: %d failure(s)\n", failures);
        return 1;
    }
    puts("VLED P5 probe: T-POLL-01..07 passed");
    return 0;
}

#endif
