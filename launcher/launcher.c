/*
 * Copyright (C) 2011-2022 Vinay Sajip. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

// This file is taken from https://github.com/pypa/distlib/blob/0.3.7/PC/launcher.c.
// You can diff the files to see the changes.
#ifndef _WIN32_WINNT            // Specifies that the minimum required platform is Windows Vista.
#define _WIN32_WINNT 0x0600     // Change this to the appropriate value to target other versions of Windows.
#endif

#include <stdio.h>
#include <io.h>
#include <stdlib.h>
#include <windows.h>
#include <shlwapi.h>

#pragma comment (lib, "shlwapi.lib")

#define MSGSIZE 1024

#if !defined(APPENDED_ARCHIVE)

static wchar_t suffix[] = {
#if defined(_CONSOLE)
    L"-script.py"
#else
    L"-script.pyw"
#endif
};

#endif

#if defined(SUPPORT_RELATIVE_PATH)

#define RELATIVE_PREFIX L"<launcher_dir>\\"
#define RELATIVE_PREFIX_LENGTH 15

#endif

#if !defined(_CONSOLE)

typedef int (__stdcall *MSGBOXWAPIA)(IN HWND hWnd,
        IN LPCSTR lpText, IN LPCSTR lpCaption,
        IN UINT uType, IN WORD wLanguageId, IN DWORD dwMilliseconds);

typedef int (__stdcall *MSGBOXWAPIW)(IN HWND hWnd,
        IN LPWSTR lpText, IN LPWSTR lpCaption,
        IN UINT uType, IN WORD wLanguageId, IN DWORD dwMilliseconds);

#define MB_TIMEDOUT 32000

int MessageBoxTimeoutA(HWND hWnd, LPCSTR lpText,
    LPCSTR lpCaption, UINT uType, WORD wLanguageId, DWORD dwMilliseconds)
{
    static MSGBOXWAPIA MsgBoxTOA = NULL;
    HMODULE hUser = LoadLibraryA("user32.dll");

    if (!MsgBoxTOA) {
        if (hUser)
            MsgBoxTOA = (MSGBOXWAPIA)GetProcAddress(hUser,
                                      "MessageBoxTimeoutA");
        else {
            /*
             * stuff happened, add code to handle it here
             * (possibly just call MessageBox())
             */
        }
    }

    if (MsgBoxTOA)
        return MsgBoxTOA(hWnd, lpText, lpCaption, uType, wLanguageId,
                         dwMilliseconds);
    if (hUser)
        FreeLibrary(hUser);
    return 0;
}

int MessageBoxTimeoutW(HWND hWnd, LPWSTR lpText,
    LPWSTR lpCaption, UINT uType, WORD wLanguageId, DWORD dwMilliseconds)
{
    static MSGBOXWAPIW MsgBoxTOW = NULL;
    HMODULE hUser = LoadLibraryA("user32.dll");

    if (!MsgBoxTOW) {
        if (hUser)
            MsgBoxTOW = (MSGBOXWAPIW)GetProcAddress(hUser,
                                      "MessageBoxTimeoutW");
        else {
            /*
             * stuff happened, add code to handle it here
             * (possibly just call MessageBox())
             */
        }
    }

    if (MsgBoxTOW)
        return MsgBoxTOW(hWnd, lpText, lpCaption, uType, wLanguageId,
                         dwMilliseconds);
    if (hUser)
        FreeLibrary(hUser);
    return 0;
}

#endif

static void
wassert(BOOL condition, wchar_t * format, ... )
{
    if (!condition) {
        va_list va;
        wchar_t message[MSGSIZE];
        int len;

        va_start(va, format);
        len = _vsnwprintf_s(message, MSGSIZE, MSGSIZE - 1, format, va);
#if defined(_CONSOLE)
        fwprintf(stderr, L"Fatal error in launcher: %s\n", message);
#else
        MessageBoxTimeoutW(NULL, message, L"Fatal Error in Launcher",
                           MB_OK | MB_SETFOREGROUND | MB_ICONERROR,
                           0, 3000);
#endif
        ExitProcess(1);
    }
}

static void
assert(BOOL condition, char * format, ... )
{
    if (!condition) {
        va_list va;
        char message[MSGSIZE];
        int len;

        va_start(va, format);
        len = vsnprintf_s(message, MSGSIZE, MSGSIZE - 1, format, va);
#if defined(_CONSOLE)
        fprintf(stderr, "Fatal error in launcher: %s\n", message);
#else
        MessageBoxTimeoutA(NULL, message, "Fatal Error in Launcher",
                           MB_OK | MB_SETFOREGROUND | MB_ICONERROR,
                           0, 3000);
#endif
        ExitProcess(1);
    }
}

static wchar_t script_path[MAX_PATH];

#if defined(APPENDED_ARCHIVE)

#define LARGE_BUFSIZE (65 * 1024 * 1024)

typedef struct {
    DWORD sig;
    DWORD unused_disk_nos;
    DWORD unused_numrecs;
    DWORD cdsize;
    DWORD cdoffset;
} ENDCDR;

/* We don't want to pick up this variable when scanning the executable.
 * So we initialise it statically, but fill in the first byte later.
 */
static char
end_cdr_sig [4] = { 0x00, 0x4B, 0x05, 0x06 };

static char *
find_pattern(char *buffer, size_t bufsize, char * pattern, size_t patsize)
{
    char * result = NULL;
    char * p;
    char * bp = buffer;
    size_t n;

    while ((n = bufsize - (bp - buffer) - patsize) >= 0) {
        p = (char *) memchr(bp, pattern[0], n);
        if (p == NULL)
            break;
        if (memcmp(pattern, p, patsize) == 0) {
            result = p; /* keep trying - we want the last one */
        }
        bp = p + 1;
    }
    return result;
}

static char *
find_shebang(char * buffer, size_t bufsize)
{
    FILE * fp = NULL;
    errno_t rc;
    char * result = NULL;
    char * p;
    size_t read;
    long pos;
    __int64 file_size;
    __int64 end_cdr_offset = -1;
    ENDCDR end_cdr;

    rc = _wfopen_s(&fp, script_path, L"rb");
    assert(rc == 0, "Failed to open executable");
    fseek(fp, 0, SEEK_END);
    file_size = ftell(fp);
    pos = (long) (file_size - bufsize);
    if (pos < 0)
        pos = 0;
    fseek(fp, pos, SEEK_SET);
    read = fread(buffer, sizeof(char), bufsize, fp);
    p = find_pattern(buffer, read, end_cdr_sig, sizeof(end_cdr_sig));
    if (p != NULL) {
        end_cdr = *((ENDCDR *) p);
        end_cdr_offset = pos + (p - buffer);
    }
    else {
        /*
         * Try a larger buffer. A comment can only be 64K long, so
         * go for the largest size.
         */
        char * big_buffer = malloc(LARGE_BUFSIZE);
        int n = (int) LARGE_BUFSIZE;

        pos = (long) (file_size - n);

        if (pos < 0)
            pos = 0;
        fseek(fp, pos, SEEK_SET);
        read = fread(big_buffer, sizeof(char), n, fp);
        p = find_pattern(big_buffer, read, end_cdr_sig, sizeof(end_cdr_sig));
        assert(p != NULL, "Unable to find an appended archive.");
        end_cdr = *((ENDCDR *) p);
        end_cdr_offset = pos + (p - big_buffer);
        free(big_buffer);
    }
    end_cdr_offset -= end_cdr.cdsize + end_cdr.cdoffset;
    /*
     * end_cdr_offset should now be pointing to the start of the archive.
     * However, the "start of the archive" is a little ill-defined, as
     * not all means of prepending data to a zipfile handle the central
     * directory offset the same way (simple file content appends leave
     * it alone, obviously, but the stdlib zipapp and zipfile modules
     * reflect the prepended data in the offset).
     * We consider two possibilities here:
     * 1. end_cdr_offset points to the start of the shebang (zipapp)
     * 2. end_cdr_offset points to the end of the shebang (data copy)
     * We'll assume the shebang line has no # or ! chars except at the
     * beginning, and fits into bufsize (which should be MAX_PATH).
     */

    /* Check for case 1 - we are at the start of the shebang */
    fseek(fp, (long) end_cdr_offset, SEEK_SET);
    read = fread(buffer, sizeof(char), bufsize, fp);
    assert(read > 0, "Unable to read from file");
    if (memcmp(buffer, "#!", 2) == 0) {
        result = buffer;
    }
    else {
        /* We are not at the start, so check backward bufsize bytes */
        pos = (long) (end_cdr_offset - bufsize);
        if (pos < 0)
            pos = 0;
        fseek(fp, pos, SEEK_SET);
        read = fread(buffer, sizeof(char), bufsize, fp);
        assert(read > 0, "Unable to read from file");
        p = &buffer[read - 1];
        while (p >= buffer) {
            if (memcmp(p, "#!", 2) == 0) {
                result = p;
                break;
            }
            --p;
        }
    }
    fclose(fp);
    return result;
}

#endif

#if defined(USE_ENVIRONMENT)
/*
 * Where to place any executable found on the path. Should be OK to use a
 * static as there's only one of these per invocation of this executable.
 */
static wchar_t path_executable[MSGSIZE];

static BOOL find_on_path(wchar_t * name)
{
    wchar_t * pathext;
    size_t    varsize;
    wchar_t * context = NULL;
    wchar_t * extension;
    DWORD     len;
    errno_t   rc;
    BOOL found = FALSE;

    if (wcschr(name, L'.') != NULL) {
        /* assume it has an extension. */
        if (SearchPathW(NULL, name, NULL, MSGSIZE, path_executable, NULL))
            found = TRUE;
    }
    else {
        /* No extension - search using registered extensions. */
        rc = _wdupenv_s(&pathext, &varsize, L"PATHEXT");
        _wcslwr_s(pathext, varsize);
        if (rc == 0) {
            extension = wcstok_s(pathext, L";", &context);
            while (extension) {
                len = SearchPathW(NULL, name, extension, MSGSIZE, path_executable, NULL);
                if (len) {
                    found = TRUE;
                    break;
                }
                extension = wcstok_s(NULL, L";", &context);
            }
            free(pathext);
        }
    }
    return found;
}

/*
 * Find an executable in the environment. For now, we just look in the path,
 * but potentially we could expand this to look in the registry, etc.
 */
static wchar_t *
find_environment_executable(wchar_t * line) {
    BOOL found = find_on_path(line);

    return found ? path_executable : NULL;
}

#endif

static wchar_t *
skip_ws(wchar_t *p)
{
    while (*p && iswspace(*p))
        ++p;
    return p;
}

static wchar_t *
skip_me(wchar_t * p)
{
    wchar_t * result;
    wchar_t terminator;

    if (*p != L'\"')
        terminator = L' ';
    else {
        terminator = *p++;
        ++p;
    }
    result = wcschr(p, terminator);
    if (result == NULL) /* perhaps nothing more on the command line */
        result = L"";
    else
        result = skip_ws(++result);
    return result;
}

static char *
find_terminator(char *buffer, size_t size)
{
    char c;
    char * result = NULL;
    char * end = buffer + size;
    char * p;

    for (p = buffer; p < end; p++) {
        c = *p;
        if (c == '\r') {
            result = p;
            break;
        }
        if (c == '\n') {
            result = p;
            break;
        }
    }
    return result;
}

#if defined(DUPLICATE_HANDLES)

static BOOL
safe_duplicate_handle(HANDLE in, HANDLE * pout)
{
    BOOL ok;
    HANDLE process = GetCurrentProcess();
#if defined(_CONSOLE)
    DWORD rc;
#endif

    *pout = NULL;
    /*
     * See https://github.com/pypa/pip/issues/10444 - for the GUI launcher,
     * errors are returned by DuplicateHandle. There may be no good reason
     * why a GUI process would want to use these handles, but for now we
     * attempt duplication but ignore errors in the GUI case.
     */
    ok = DuplicateHandle(process, in, process, pout, 0, TRUE,
                         DUPLICATE_SAME_ACCESS);
#if defined(_CONSOLE)
    if (!ok) {
        rc = GetLastError();
        if (rc == ERROR_INVALID_HANDLE)
            ok = TRUE;
    }
    return ok;
#else
    return TRUE;
#endif
}

#endif

/*
 * These items are global so that thet can be accessed
 * from the Ctrl-C handler or other auxiliary routine.
 */
static PROCESS_INFORMATION child_process_info;
static JOBOBJECT_EXTENDED_LIMIT_INFORMATION job_info;
static HANDLE job;

static BOOL
control_key_handler(DWORD type)
{
/*
 * See https://github.com/pypa/pip/issues/10444
 */
#if defined(OLD_LOGIC)
    if ((type == CTRL_C_EVENT) || (type == CTRL_BREAK_EVENT)) {
        return TRUE;
    }
    WaitForSingleObject(child_process_info.hProcess, INFINITE);
#else
    switch (type) {
    case CTRL_CLOSE_EVENT:
    case CTRL_LOGOFF_EVENT:
    case CTRL_SHUTDOWN_EVENT:
        /*
         * Allow the child to outlive the launcher, to carry out any
         * cleanup for a graceful exit. It will either exit or get
         * terminated by the session server.
         */
        if (job != NULL) {
            job_info.BasicLimitInformation.LimitFlags &=
              ~JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            SetInformationJobObject(
              job, JobObjectExtendedLimitInformation,
              &job_info, sizeof(job_info));
        }
    }
#endif
    return TRUE;
}

#if !defined(_CONSOLE)

/*
 * End the launcher's "app starting" cursor state.
 *
 * When Explorer launches a Windows (GUI) application, it displays
 * the "app starting" (the "pointer + hourglass") cursor for a number
 * of seconds, or until the app does something UI-ish (eg, creating a
 * window, or fetching a message).  As this launcher doesn't do this
 * directly, that cursor remains even after the child process does these
 * things.  We avoid that by doing the stuff in here.
 * See http://bugs.python.org/issue17290 and
 * https://github.com/pypa/pip/issues/10444#issuecomment-973408601
 */

static void
clear_app_starting_state() {
    MSG msg;
    HWND hwnd;

    PostMessageW(0, 0, 0, 0);
    GetMessageW(&msg, 0, 0, 0);
    /* Proxy the child's input idle event. */
    WaitForInputIdle(child_process_info.hProcess, INFINITE);
    /*
     * Signal the process input idle event by creating a window and pumping
     * sent messages. The window class isn't important, so just use the
     * system "STATIC" class.
     */
    hwnd = CreateWindowExW(0, L"STATIC", L"PyLauncher", 0, 0, 0, 0, 0,
                           HWND_MESSAGE, NULL, NULL, NULL);
    /* Process all sent messages and signal input idle. */
    PeekMessageW(&msg, hwnd, 0, 0, 0);
    DestroyWindow(hwnd);
}

#endif

/*
 * See https://github.com/pypa/pip/issues/10444#issuecomment-1055392299
 */
static BOOL
make_handle_inheritable(HANDLE handle)
{
    DWORD file_type = GetFileType(handle);
    // Ignore an invalid handle, non-file object type, unsupported file type,
    // or a console file prior to Windows 8.
    if (file_type == FILE_TYPE_UNKNOWN ||
        (file_type == FILE_TYPE_CHAR && ((ULONG_PTR)handle & 3))) {
        return TRUE;
    }

    return SetHandleInformation(handle, HANDLE_FLAG_INHERIT,
        HANDLE_FLAG_INHERIT);
}

static void
__cdecl
silent_invalid_parameter_handler(
    wchar_t const* expression,
    wchar_t const* function,
    wchar_t const* file,
    unsigned int line,
    uintptr_t pReserved
)
{
}

/*
 * Best-effort cleanup of any C file descriptors that were inherited
 * from the parent process. This cleans up all fds except 0-2.
 */
static void
cleanup_fds(WORD cbReserved2, LPBYTE lpReserved2)
{
    int handle_count = 0;
    UNALIGNED HANDLE* first_handle = NULL;
    UNALIGNED HANDLE* current_handle = NULL;
    _invalid_parameter_handler old_handler = NULL;

    // The structure is: <handle_count>, <handle_count bytes with flags>, <handle_count HANDLEs>

    if (cbReserved2 < sizeof(int) || NULL == lpReserved2)
    {
        return;
    }

    handle_count = *(UNALIGNED int*)lpReserved2;

    // Verify the buffer is large enough
    if (cbReserved2 < sizeof(int) + handle_count + sizeof(HANDLE) * handle_count)
    {
        return;
    }

    first_handle = (UNALIGNED HANDLE *)(lpReserved2 + sizeof(int) + handle_count);

    old_handler = _set_invalid_parameter_handler(&silent_invalid_parameter_handler);
    {
        // Close all fds inherited from the parent, except for the standard I/O fds.
        // We'll deal with those later.
        for (current_handle = first_handle + 3; current_handle < first_handle + handle_count; ++current_handle)
        {
            // Ignore invalid handles, as that means this fd was not inherited.
            // -2 is a special value (https://docs.microsoft.com/en-us/cpp/c-runtime-library/reference/get-osfhandle?view=msvc-170)
            // that we check for just in case.
            if (NULL == *current_handle || INVALID_HANDLE_VALUE == *current_handle || (HANDLE)-2 == *current_handle)
            {
                continue;
            }

            _close((int)(current_handle - first_handle));
        }
    }
    _set_invalid_parameter_handler(old_handler);
}

/*
 * Returns the HANDLE associated with a FILE* object, or INVALID_HANDLE_VALUE
 * on error.
 */
static HANDLE
get_stream_handle(FILE * stream)
{
    _invalid_parameter_handler old_handler = NULL;
    int fd = -1;
    HANDLE handle = INVALID_HANDLE_VALUE;

    old_handler = _set_invalid_parameter_handler(&silent_invalid_parameter_handler);
    {
        fd = _fileno(stream);
        if (fd >= 0)
        {
            handle = (HANDLE)_get_osfhandle(fd);
        }
        else
        {
            handle = INVALID_HANDLE_VALUE;
        }
    }
    _set_invalid_parameter_handler(old_handler);

    return handle;
}

/*
 * Closes the Windows standard I/O handles (GetStdHandle)
 * in a best-effort manner. Ensures that the stderr stream is left untouched.
 */
static void
cleanup_standard_io(void)
{
    HANDLE stdin_handle = INVALID_HANDLE_VALUE;
    HANDLE stdout_handle = INVALID_HANDLE_VALUE;
    HANDLE stderr_handle = INVALID_HANDLE_VALUE;
    HANDLE hStdIn = INVALID_HANDLE_VALUE;
    HANDLE hStdOut = INVALID_HANDLE_VALUE;
    HANDLE hStdErr = INVALID_HANDLE_VALUE;

    // We need to close both the C streams stdin and stdout,
    // and the Windows standard I/O handles. However, these may be equal,
    // so care must be taken not to close a handle twice. Moreover,
    // handles for several C streams may be equal as well.
    // Fun all around.

    // Get the handles associated with the standard I/O streams.
    stdin_handle = get_stream_handle(stdin);
    stdout_handle = get_stream_handle(stdout);
    stderr_handle = get_stream_handle(stderr);

    // If any two underlying handles are equal, drop everything and return.
    // There's bound to be trouble if we continue with closing the streams.
    if (((INVALID_HANDLE_VALUE != stdin_handle) && (stdin_handle == stdout_handle || stdin_handle == stderr_handle))
        || ((INVALID_HANDLE_VALUE != stdout_handle) && (stdout_handle == stdin_handle || stdout_handle == stderr_handle))
        || ((INVALID_HANDLE_VALUE != stderr_handle) && (stderr_handle == stdin_handle || stderr_handle == stdout_handle)))
    {
        return;
    }

    // Get the Windows I/O handles before we do anything.
    hStdIn = GetStdHandle(STD_INPUT_HANDLE);
    hStdOut = GetStdHandle(STD_OUTPUT_HANDLE);
    hStdErr = GetStdHandle(STD_ERROR_HANDLE);

    // At this point, we have confirmed that the I/O streams all have different
    // handles, and we have the Windows standard I/O handles as well.
    // Proceed with closing the streams.

    fclose(stdin);
    fclose(stdout);

    // Now we need to close the Windows standard I/O handles, as they might
    // differ from the handles for the C streams.

    // First, make sure we don't close handles that we have already closed
    // by closing the streams.
    if (stdin_handle == hStdIn || stdout_handle == hStdIn)
    {
        SetStdHandle(STD_INPUT_HANDLE, NULL);
        hStdIn = NULL;
    }
    if (stdin_handle == hStdOut || stdout_handle == hStdOut)
    {
        SetStdHandle(STD_OUTPUT_HANDLE, NULL);
        hStdOut = NULL;
    }
    if (stdin_handle == hStdErr || stdout_handle == hStdErr)
    {
        SetStdHandle(STD_ERROR_HANDLE, NULL);
        hStdErr = NULL;
    }

    // Ensure we don't accidentally close the standard error handle.
    if (stderr_handle == hStdIn)
    {
        hStdIn = NULL;
    }
    if (stderr_handle == hStdOut)
    {
        hStdOut = NULL;
    }
    if (stderr_handle == hStdErr)
    {
        hStdErr = NULL;
    }

    // Close 'em.
    if (NULL != hStdIn && INVALID_HANDLE_VALUE != hStdIn)
    {
        CloseHandle(hStdIn);
        SetStdHandle(STD_INPUT_HANDLE, NULL);
    }
    if (NULL != hStdOut && INVALID_HANDLE_VALUE != hStdOut)
    {
        CloseHandle(hStdOut);
        SetStdHandle(STD_OUTPUT_HANDLE, NULL);
    }
    if (NULL != hStdErr && INVALID_HANDLE_VALUE != hStdErr)
    {
        CloseHandle(hStdErr);
        SetStdHandle(STD_ERROR_HANDLE, NULL);
    }
}

#define SWITCH_WORKING_DIR

#if defined(SWITCH_WORKING_DIR)

/*
 * Switch the working directory to the user's temp directory.
 */

static void
switch_working_directory() {
    WCHAR tempDir[MAX_PATH + 1];
    DWORD len = GetTempPathW(MAX_PATH + 1, tempDir);
    if (len > 0 && len <= MAX_PATH) {
        SetCurrentDirectoryW(tempDir);
    }
}
#endif

/*
 * Best-effort cleanup of file descriptors and handles after spawning the child
 * process.
 * See discussion starting from here: https://github.com/pypa/pip/issues/10444#issuecomment-1055392299
 */
static void
post_spawn_cleanup(WORD cbReserved2, LPBYTE lpReserved2)
{
    cleanup_fds(cbReserved2, lpReserved2);

    cleanup_standard_io();
#if defined(SWITCH_WORKING_DIR)
    switch_working_directory();
#endif
}

/*
 * See https://github.com/pypa/pip/issues/10444#issuecomment-971921420
 */
#define STARTF_UNDOC_MONITOR 0x400
/*
 * See https://github.com/pypa/pip/issues/10444#issuecomment-973396812
 */

static void
run_child(wchar_t * cmdline)
{
    DWORD rc;
    BOOL ok;
    STARTUPINFOW si;

    job = CreateJobObject(NULL, NULL);
    assert(job != NULL, "Job creation failed");
    ok = QueryInformationJobObject(job, JobObjectExtendedLimitInformation,
                                  &job_info, sizeof(job_info), &rc);
    assert(ok && (rc == sizeof(job_info)), "Job information querying failed");
    job_info.BasicLimitInformation.LimitFlags |= JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                                                 JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK;
    ok = SetInformationJobObject(job, JobObjectExtendedLimitInformation, &job_info,
                                 sizeof(job_info));
    assert(ok, "Job information setting failed");
    memset(&si, 0, sizeof(si));
    GetStartupInfoW(&si);
/*
 * See https://github.com/pypa/pip/issues/10444#issuecomment-973396812
 */
    if ((si.dwFlags & (STARTF_USEHOTKEY | STARTF_UNDOC_MONITOR)) == 0) {
        HANDLE hIn = GetStdHandle(STD_INPUT_HANDLE);
        HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
        HANDLE hErr = GetStdHandle(STD_ERROR_HANDLE);

#if defined(DUPLICATE_HANDLES)
        ok = safe_duplicate_handle(hIn, &si.hStdInput);
        assert(ok, "stdin duplication failed");
        CloseHandle(hIn);

        ok = safe_duplicate_handle(hOut, &si.hStdOutput);
        assert(ok, "stdout duplication failed");
        CloseHandle(hOut);
        /* We might need stderr late, so don't close it but mark as non-inheritable */
        SetHandleInformation(hErr, HANDLE_FLAG_INHERIT, 0);

        ok = safe_duplicate_handle(hErr, &si.hStdError);
        assert(ok, "stderr duplication failed");
#else
        /*
         * See https://github.com/pypa/pip/issues/10444#issuecomment-1055392299
         */
        ok = make_handle_inheritable(hIn);
        assert(ok, "making stdin inheritable failed");
        ok = make_handle_inheritable(hOut);
        assert(ok, "making stdout inheritable failed");
        ok = make_handle_inheritable(hErr);
        assert(ok, "making stderr inheritable failed");
        si.hStdInput = hIn;
        si.hStdOutput = hOut;
        si.hStdError = hErr;
#endif
        si.dwFlags |= STARTF_USESTDHANDLES;
    }

    size_t rez_envvar_size = 0;
    getenv_s(&rez_envvar_size, NULL, 0, "REZ_LAUNCHER_DEBUG");
    if (rez_envvar_size > 0) {
        printf("Launching: %ls\n", cmdline);
    }

    ok = CreateProcessW(NULL, cmdline, NULL, NULL, TRUE, 0, NULL, NULL, &si, &child_process_info);
    if (!ok) {
        // Failed to create process. See if we can find out why.
        DWORD err = GetLastError();
        wchar_t emessage[MSGSIZE];
        FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM, NULL, err,
                       MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), emessage, MSGSIZE, NULL);
        wassert(ok, L"Unable to create process using '%ls': %ls", cmdline, emessage);
    }
    // Assign the process to the job straight away. See https://github.com/pypa/distlib/issues/175
    AssignProcessToJobObject(job, child_process_info.hProcess);
    post_spawn_cleanup(si.cbReserved2, si.lpReserved2);
    /*
     * Control handler setting is now done after process creation because the handler needs access
     * to the child_process_info structure, which is populated by the CreateProcessW call above.
     */
    ok = SetConsoleCtrlHandler((PHANDLER_ROUTINE) control_key_handler, TRUE);
    assert(ok, "control handler setting failed");
#if !defined(_CONSOLE)
    clear_app_starting_state(&child_process_info);
#endif
    CloseHandle(child_process_info.hThread);
    WaitForSingleObjectEx(child_process_info.hProcess, INFINITE, FALSE);
    ok = GetExitCodeProcess(child_process_info.hProcess, &rc);
    assert(ok, "Failed to get exit code of process");
    ExitProcess(rc);
}

static wchar_t *
find_exe_extension(wchar_t * line) {
    wchar_t * p;

    while ((p = StrStrIW(line, L".exe")) != NULL) {
        wchar_t c = p[4];

        if ((c == L'\0') || (c == L'"') || iswspace(c))
            break;
        line = &p[4];
    }
    return p;
}

static wchar_t *
find_executable_and_args(wchar_t * line, wchar_t ** argp)
{
    wchar_t * p = find_exe_extension(line);
#if defined(USE_ENVIRONMENT)
    wchar_t * q;
    int n;
#endif
    wchar_t * result;

#if !defined(USE_ENVIRONMENT)
    assert(p != NULL, "Expected to find a command ending in '.exe' in shebang line: %ls", line);
    p += 4; /* skip past the '.exe' */
    result = line;
#else
    if (p != NULL) {
        p += 4; /* skip past the '.exe' */
        result = line;
    }
    else {
        n = _wcsnicmp(line, L"/usr/bin/env", 12);
        assert(n == 0, "Expected to find a command ending in '.exe' in shebang line: %ls", line);
        p = line + 12; /* past the '/usr/bin/env' */
        assert(*p && iswspace(*p), "Expected to find whitespace after '/usr/bin/env': %ls", line);
        do {
            ++p;
        } while (*p && iswspace(*p));
        /* Now, p points to what comes after /usr/bin/env and any following whitespace. */
        q = p;
        /* Skip past executable name and NUL-terminate it. */
        while (*q && !iswspace(*q))
            ++q;
        if (iswspace(*q))
            *q++ = L'\0';
        result = find_environment_executable(p);
        assert(result != NULL, "Unable to find executable in environment: %ls", line);
        p = q; /* point past name of executable in shebang */
    }
#endif
    if (*line == L'"') {
        assert(*p == L'"', "Expected terminating double-quote for executable in shebang line: %ls", line);
        *p++ = L'\0';
        ++line;
        ++result;  /* See https://bitbucket.org/pypa/distlib/issues/104 */
    }
    /* p points just past the executable. It must either be a NUL or whitespace. */
#if !defined(SUPPORT_RELATIVE_PATH)
    assert(*p != L'"', "Terminating quote without starting quote for executable in shebang line: %ls", line);
#else
    if (_wcsnicmp(line, RELATIVE_PREFIX, RELATIVE_PREFIX_LENGTH) && (line[RELATIVE_PREFIX_LENGTH] != L'\"')) {
        assert(*p != L'"', "Terminating quote without starting quote for executable in shebang line: %ls", line);
    }
#endif
    /* if p is whitespace, make it NUL to truncate 'line', and advance */
    if (*p && iswspace(*p))
        *p++ = L'\0';
    /* Now we can skip the whitespace, having checked that it's there. */
    while(*p && iswspace(*p))
        ++p;
    *argp = p;
    return result;
}

static int
process(int argc, char * argv[])
{
    wchar_t * cmdline = skip_me(GetCommandLineW());
    wchar_t * psp;
    size_t len = GetModuleFileNameW(NULL, script_path, MAX_PATH);
    FILE *fp = NULL;
    char buffer[MAX_PATH];
    wchar_t wbuffer[MAX_PATH];
#if defined(SUPPORT_RELATIVE_PATH)
    wchar_t dbuffer[MAX_PATH];
    wchar_t pbuffer[MAX_PATH];
    wchar_t * qp;
    int prefix_offset;
#endif
    char *cp;
    wchar_t * wcp;
    wchar_t * cmdp;
    char * p;
    wchar_t * wp;
    int n;
#if !defined(APPENDED_ARCHIVE)
    errno_t rc;
#endif

    if (script_path[0] != L'\"')
        psp = script_path;
    else {
        psp = &script_path[1];
        len -= 2;
    }
    psp[len] = L'\0';

#if !defined(APPENDED_ARCHIVE)
    /* Replace the .exe with -script.py(w) */
    wp = wcsstr(psp, L".exe");
    assert(wp != NULL, "Failed to find \".exe\" in executable name");

    len = MAX_PATH - (wp - script_path);
    assert(len > sizeof(suffix), "Failed to append \"%ls\" suffix", suffix);
    wcsncpy_s(wp, len, suffix, sizeof(suffix));
#endif
#if defined(APPENDED_ARCHIVE)
    /* Initialise signature dynamically so that it doesn't appear in
     * a stock executable.
     */
    end_cdr_sig[0] = 0x50;

    p = find_shebang(buffer, MAX_PATH);
    assert(p != NULL, "Failed to find shebang");
#else
    rc = _wfopen_s(&fp, psp, L"rb");
    assert(rc == 0, "Failed to open script file '%ls'", psp);
    fread(buffer, sizeof(char), MAX_PATH, fp);
    fclose(fp);
    p = buffer;
#endif
    cp = find_terminator(p, MAX_PATH);
    assert(cp != NULL, "Expected to find terminator in shebang line");
    *cp = '\0';
    // Decode as UTF-8
    n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, p, (int) (cp - p), wbuffer, MAX_PATH);
    assert(n != 0, "Expected to decode shebang line using UTF-8");
    wbuffer[n] = L'\0';
    wcp = wbuffer;
    while (*wcp && iswspace(*wcp))
        ++wcp;
    assert(*wcp == L'#', "Expected to find \'#\' at start of shebang line");
    ++wcp;
    while (*wcp && iswspace(*wcp))
        ++wcp;
    assert(*wcp == L'!', "Expected to find \'!\' following \'#\' in shebang line");
    ++wcp;
    while (*wcp && iswspace(*wcp))
        ++wcp;
    wp = NULL;
    wcp = find_executable_and_args(wcp, &wp);
    assert(wcp != NULL, "Expected to find executable in shebang line");
    assert(wp != NULL, "Expected to find arguments (even if empty) in shebang line");
#if defined(SUPPORT_RELATIVE_PATH)
    /*
       If the executable starts with the relative prefix, resolve the following path
       relative to the launcher's directory.
     */
    prefix_offset = RELATIVE_PREFIX_LENGTH;
    if (!_wcsnicmp(RELATIVE_PREFIX, wcp, prefix_offset)) {
        wcscpy_s(dbuffer, MAX_PATH, script_path);
        PathRemoveFileSpecW(dbuffer);
        if (wcp[prefix_offset] == L'\"') {
            prefix_offset++;
            qp = wcschr(&wcp[prefix_offset], L'\"');
            assert(qp != NULL, "Expected terminating double-quote for executable in shebang line: %ls", wcp);
            *qp = L'\0';
        }
        // The following call appears to canonicalize the path, so no need to
        // worry about doing that
        PathCombineW(pbuffer, dbuffer, &wcp[prefix_offset]);
        wcp = pbuffer;
    }
#endif
     /* 4 spaces + 4 quotes + -E + NUL */
    len = wcslen(wcp) + wcslen(wp) + 11 + wcslen(psp) + wcslen(cmdline);
    cmdp = (wchar_t *) calloc(len, sizeof(wchar_t));
    assert(cmdp != NULL, "Expected to be able to allocate command line memory");
    // Note that we inject -E to make sure PYTHON* variables are not picked up.
    _snwprintf_s(cmdp, len, len, L"\"%ls\" -E %ls \"%ls\" %ls", wcp, wp, psp, cmdline);
    run_child(cmdp);  /* never actually returns */
    free(cmdp);
    return 0;
}

#if defined(_CONSOLE)

int main(int argc, char* argv[])
{
    return process(argc, argv);
}

#else

int APIENTRY WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                     LPSTR lpCmdLine, int nCmdShow)
{
    return process(__argc, __argv);
}

#endif
