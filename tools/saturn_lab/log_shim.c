/* Independent libretro variadic-log adapter. Apache-2.0, Neptune contributors.
 * Never call a variadic C logger directly through a fixed ctypes callback. */
#include <stdarg.h>
#include <stdio.h>

static void (*log_sink)(int, const char *);

void neptune_set_log_sink(void (*sink)(int, const char *)) {
    log_sink = sink;
}

void neptune_log(int level, const char *format, ...) {
    char buffer[4096];
    va_list arguments;
    va_start(arguments, format);
    vsnprintf(buffer, sizeof(buffer), format, arguments);
    va_end(arguments);
    if (log_sink) log_sink(level, buffer);
}
