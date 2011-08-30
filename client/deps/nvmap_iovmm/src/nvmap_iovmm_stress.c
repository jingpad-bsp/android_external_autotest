/*
 * Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file.
 */

#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>

#include <stdlib.h>
#include <unistd.h>
#include <getopt.h>
#include <stdio.h>
#include <math.h>
#include <sys/time.h>
#include <string.h>
#include <stdbool.h>
#include <assert.h>

const char vertex_src [] =
"                                               \
uniform mat4 transformMatrix;                   \
attribute vec4 position;                        \
attribute vec4 tcoord;                          \
varying vec2 st;                                \
                                                \
void main()                                     \
{                                               \
    gl_Position = transformMatrix * position;   \
    st = tcoord.st;                             \
}                                               \
";

const char fragment_src [] =
"                                               \
precision highp float;                          \
uniform sampler2D tex;                          \
varying vec2 st;                                \
                                                \
void main()                                     \
{                                               \
    gl_FragColor = texture2D(tex, st);          \
}                                               \
";

#define TEST_WIDTH  256
#define TEST_HEIGHT 256

#define TEXTURE_WIDTH 2048
#define TEXTURE_HEIGHT 2048
#define TEXTURE_COUNT 32
#define TEXTURE_DEFAULT_X 0
#define TEXTURE_DEFAULT_Y 0
#define DEFAULT_LOOP_COUNT 100

static const GLfloat sVertData[] = {
        -1, -1, 0, 1,
        1, -1, 0, 1,
        -1,  1, 0, 1,
        1,  1, 0, 1
};

static GLuint vertex_obj, fragment_obj, program_obj;
int verbose = 0;

static Display *x_display;
static Window win;
static EGLDisplay egl_display;
static EGLContext egl_context;
static EGLSurface egl_surface;

/*
 * This function creates an RGBA texture with a given width and height.
 * It also takes in a number which is used to give the texture a slightly
 * different shade of blue to be able to distinguish visually between
 * different textures.
 * Return value: handle to texture
 */
static GLuint CreateTexture(int width, int height, int number)
{
        char *data = NULL;
        int x, y, bytes_per_pixel;
        GLuint tex;

        assert(number == (number & 0xF));

        // There are 4 bytes per pixel for GL_RGBA & GL_UNSIGNED_BYTE
        bytes_per_pixel = 4;

        data = (char *)malloc((size_t)(width*height*bytes_per_pixel));
        if (!data)
                return -1;

        for (x = 0; x < width; x++) {
                for (y = 0 ; y < height; y++) {
                        int idx = (y*width + x)*bytes_per_pixel;
                        data[idx] = (number * 0xF) & 0xFF;
                        data[idx+1] = (number * 0xF) & 0xFF;
                        data[idx+2] = 0xFF;
                        data[idx+3] = 0xFF;
                }
        }

        // create texture
        glGenTextures(1, &tex);
        if (glGetError() !=  GL_NO_ERROR)
                goto fail;

        glActiveTexture(GL_TEXTURE0);
        if (glGetError() !=  GL_NO_ERROR)
                goto fail;

        glBindTexture(GL_TEXTURE_2D, tex);
        if (glGetError() !=  GL_NO_ERROR)
                goto fail;

        glTexImage2D(
                /* target */            GL_TEXTURE_2D,
                /* level */             0,
                /* internalformat */    (GLint)GL_RGBA,
                /* width */             width,
                /* height */            height,
                /* border */            0,
                /* format */            GL_RGBA,
                /* type */              GL_UNSIGNED_BYTE,
                /* pixels */            data);
        if (glGetError() !=  GL_NO_ERROR)
                goto fail;

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

        goto done;

fail:
        tex = -1;
done:
        free(data);

        return tex;
}

/*
 * Filling in the result array with an identity matrix.
 */
static void LoadIdentity(GLfloat *result)
{
        memset(result, 0x0, 16*4);
        result[0] = 1;
        result[5] = 1;
        result[10] = 1;
        result[15] = 1;
}

/*
 * Create a scaling matrix.
 */
static void Scale(GLfloat *result, GLfloat sx, GLfloat sy, GLfloat sz)
{
        result[0] *= sx;
        result[1] *= sx;
        result[2] *= sx;
        result[3] *= sx;

        result[4] *= sy;
        result[5] *= sy;
        result[6] *= sy;
        result[7] *= sy;

        result[8] *= sz;
        result[9] *= sz;
        result[10] *= sz;
        result[11] *= sz;
}

/*
 * Creates a translation matrix.
 */
static void Translate(GLfloat *result, GLfloat tx, GLfloat ty, GLfloat tz)
{
        result[12] += (result[0] * tx + result[4] * ty + result[8] * tz);
        result[13] += (result[1] * tx + result[5] * ty + result[9] * tz);
        result[14] += (result[2] * tx + result[6] * ty + result[10] * tz);
        result[15] += (result[3] * tx + result[7] * ty + result[11] * tz);
}

/*
 * This function runs the actual test, drawing the texture rects.
 * Return value: 0 on success
 */
static int RunTest(int width, int height)
{
        GLuint tex[TEXTURE_COUNT];
        GLint texSampler;
        GLint transformMatrixUniform;
        GLfloat vertSTData[8];
        int i, j;
        GLfloat transformMatrix[16];
        int cols = (int)sqrtf(TEXTURE_COUNT);
        struct timeval tv;
        int rnd;

        gettimeofday(&tv, NULL);
        rnd = tv.tv_sec * 1000;

        glViewport(0, 0, width, height);
        glClear(GL_COLOR_BUFFER_BIT);

        // Create texture
        for (i = 0; i < TEXTURE_COUNT; i++) {
                if (verbose)
                        printf("Allocating texture %d\n", i);
                tex[i] = CreateTexture(width / (1 + TEXTURE_COUNT - i),
                                height / (1 + TEXTURE_COUNT - i), (i % 16));
        }

        // Texture coords
        vertSTData[0] = 0;
        vertSTData[1] = 0;
        vertSTData[2] = width;
        vertSTData[3] = 0;
        vertSTData[4] = 0;
        vertSTData[5] = height;
        vertSTData[6] = width;
        vertSTData[7] = height;

        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 0, vertSTData);
        texSampler = glGetUniformLocation(program_obj, "tex");
        transformMatrixUniform = glGetUniformLocation(program_obj,
                                        "transformMatrix");
        glUniform1i(texSampler, 0);

        // Draw texture rectangles
        for (j = 0; j < 50; j++) {
                LoadIdentity(transformMatrix);
                Scale(transformMatrix, 4.0f/cols, 4.0f/cols, 4.0f/cols);
                Translate(transformMatrix, -cols - 1.0f, cols - 1.0f, 0.0f);
                for (i = 0; i < TEXTURE_COUNT; i++) {
                    rnd = rnd * 69069 + 69069;
                    if(((rnd / 1217) & 255) > 128) {
                        Translate(transformMatrix, 2.0f, 0.0f, 0.0f);
                        glUniformMatrix4fv(transformMatrixUniform, 1, GL_FALSE,
                                                transformMatrix);
                        glBindTexture(GL_TEXTURE_2D, tex[i]);
                        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
                        if (((i+1) % cols) == 0) {
                            Translate(transformMatrix, -2.0f*cols, -2.0f,
                                        0.0f);
                        }
                    }
                }
                glFlush();
        }

        // Clean up
        for (i = 0; i < TEXTURE_COUNT; i++) {
                glDeleteTextures(1, &tex[i]);
        }

        return 0;
}

/*
 * This function prints the info log for a given shader (from handle).
 */
void PrintShaderInfoLog(GLuint shader)
{
        GLint        length;

        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &length);

        if (length) {
                char buffer[length];
                glGetShaderInfoLog(shader, length, NULL, buffer);
                printf("shader info: %s\n", buffer);
        }
}

GLuint LoadShader(const char *shader_src, GLenum type)
{
        GLuint        shader = glCreateShader(type);
        GLint         success;

        glShaderSource(shader, 1, &shader_src, NULL);
        glCompileShader(shader);
        glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
        if (success != GL_TRUE) {
                printf("FAILED to compile shader. %d\n", success);
                return success;
        }

        if (verbose)
                PrintShaderInfoLog(shader);

        return shader;
}

static void InitGraphicsState()
{
        glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 0, sVertData);
        glEnableVertexAttribArray(0);
        glEnableVertexAttribArray(1);

        vertex_obj = LoadShader(vertex_src, GL_VERTEX_SHADER);
        fragment_obj = LoadShader(fragment_src, GL_FRAGMENT_SHADER);

        program_obj = glCreateProgram();
        glAttachShader(program_obj, vertex_obj);
        glAttachShader(program_obj, fragment_obj);
        glBindAttribLocation(program_obj, 0, "position");
        glBindAttribLocation(program_obj, 1, "tcoord");
        glLinkProgram(program_obj);
        glUseProgram(program_obj);

        // so that odd-sized RGB textures will work nicely
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);

        glDisable(GL_DEPTH_TEST);
}

int XInitialize(int x, int y, int width, int height)
{
        Window                         root;
        XSetWindowAttributes         swa;
        XSetWindowAttributes         xattr;
        Atom                         atom;
        XWMHints                     hints;
        int                          xres;

        x_display = XOpenDisplay(NULL);
        if (x_display == NULL) {
                printf("Cannot connect to X server. Exiting...\n");
                return -1;
        }

        root = DefaultRootWindow(x_display);
        swa.event_mask = ExposureMask | PointerMotionMask | KeyPressMask;

        if (verbose)
                printf("Creating window at (%d,%d) with w=%d, h=%d\n",
                        x, y, width, height);

        win = XCreateWindow(
                /* connection to x server */      x_display,
                /* parent window */               root,
                /* x coord, top left corner */    x,
                /* y coord, top left corner */    y,
                /* width of window */             width,
                /* height of window */            height,
                /* border width */                0,
                /* depth of window */             CopyFromParent,
                /* window's class */              InputOutput,
                /* visual type */                 CopyFromParent,
                /* valid attribute mask */        CWEventMask,
                /* attributes */                  &swa);
        if (win == BadAlloc ||
            win == BadColor ||
            win == BadCursor ||
            win == BadMatch ||
            win == BadPixmap ||
            win == BadValue ||
            win == BadWindow) {
                printf("FAILED to create X window\n");
                return -1;
        }

        xattr.override_redirect = false;
        xres = XChangeWindowAttributes(x_display, win, CWOverrideRedirect,
                                        &xattr);
        if (xres == BadAccess ||
            xres == BadColor ||
            xres == BadCursor ||
            xres == BadMatch ||
            xres == BadPixmap ||
            xres == BadValue ||
            xres == BadWindow) {
                printf("FAIL to change X window attrib: %d\n", xres);
                goto fail;
        }

        atom = XInternAtom(x_display, "_NET_WM_STATE_FULLSCREEN", true);

        hints.input = true;
        hints.flags = InputHint;
        XSetWMHints(x_display, win, &hints);
        if (xres == BadAlloc || xres == BadWindow) {
                printf("FAIL to set X WM hints: %d\n", xres);
                goto fail;
        }

        XMapWindow(x_display, win);
        if (xres == BadWindow) {
                printf("FAIL to map X window: %d\n", xres);
                goto fail;
        }

        XStoreName(x_display, win, "GLES2 Texture Test");
        if (xres == BadAlloc || xres == BadWindow) {
                printf("FAIL to store X window name: %d\n", xres);
                goto fail;
        }

        return 0;

fail:
        XDestroyWindow(x_display, win);
        XCloseDisplay(x_display);

        return -1;
}


int EglInitialize()
{
        EGLConfig        config;
        EGLint                numConfig;

        EGLint        attr[] = {
                EGL_BUFFER_SIZE, 16,
                EGL_RENDERABLE_TYPE,
                EGL_OPENGL_ES2_BIT,
                EGL_NONE
        };

        EGLint ctxattr[] = {
                EGL_CONTEXT_CLIENT_VERSION, 2,
                EGL_NONE
        };

        egl_display = eglGetDisplay((EGLNativeDisplayType)x_display);
        if (egl_display == EGL_NO_DISPLAY) {
                printf("EGL failed to obtain display. Exiting...\n");
                return -1;
        }

        if ( !eglInitialize(egl_display, NULL, NULL)) {
                printf("EGL failed to initialize. Exiting...\n");
                return -1;
        }

        if ( !eglChooseConfig(egl_display, attr, &config, 1, &numConfig)) {
                printf("EGL failed to choose config. Exiting...\n");
                return -1;
        }

        if (numConfig != 1) {
                printf("EGL failed to get 1 config, got %d Exiting...\n",
                        numConfig);
                return -1;
        }

        egl_surface = eglCreateWindowSurface(egl_display, config, win, NULL);
        if (egl_surface == EGL_NO_SURFACE) {
                printf("EGL failed to create window surface. Exiting...\n");
                return -1;
        }

        egl_context = eglCreateContext(egl_display, config, EGL_NO_CONTEXT,
                                        ctxattr);
        if (egl_context == EGL_NO_CONTEXT) {
                printf("EGL failed to create context. Exiting...\n");
                return -1;
        }

        if ( !eglMakeCurrent(egl_display, egl_surface, egl_surface,
                                egl_context)) {
                printf("EGL failed to make context current. Exiting...\n");
                return -1;
        }

        return 0;
}

void PrintUsage()
{
        printf("--------------------------------------------\n");
        printf("nvmap_iovmm_stress [options]\n");
        printf("  --help               - Show this help screen\n");
        printf("  -x                   - Set window x coordinate[ def: %d]\n",
                TEXTURE_DEFAULT_X);
        printf("  -y                   - Set window y coordinate[ def: %d]\n",
                TEXTURE_DEFAULT_Y);
        printf("  -w --width           - Set window width  [ def: %d]\n",
                TEXTURE_WIDTH);
        printf("  -h | --height        - Set window height [ def: %d]\n",
                TEXTURE_HEIGHT);
        printf("  -i | --infinte_loop  - Enables running forever\n");
        printf("  -v | --verbose       - Enables verbose prints\n");
        printf("  -l | --loop_count    - # of times to loop [def: %d]\n",
                DEFAULT_LOOP_COUNT);
}

void CleanupX()
{
        XDestroyWindow(x_display, win);
        XCloseDisplay(x_display);
}

void CleanupEgl()
{
        eglDestroyContext(egl_display, egl_context);
        eglDestroySurface(egl_display, egl_surface);
        eglTerminate(egl_display);
}

int main(int argc, char *argv[])
{
        int failure = 0;
        int i, x = TEXTURE_DEFAULT_X, y = TEXTURE_DEFAULT_Y;
        int height = TEST_HEIGHT, width = TEST_WIDTH;
        int loop_count = DEFAULT_LOOP_COUNT;
        int option_index = 0;
        GLenum err_code;

        static struct option long_options[] = {
                {"help",          no_argument,        0,        'p'},
                {"verbose",       no_argument,        0,        'v'},
                {"width",         required_argument,  0,        'w'},
                {"height",        required_argument,  0,        'h'},
                {"loop_count",    required_argument,  0,        'l'},
                {NULL,            0,                  NULL,     0}
        };

        if (!getenv("DISPLAY")) {
                printf("DISPLAY environmental variable not set.\n");
                failure = -1;
                goto done;
        }

        while ((i = getopt_long(argc, argv, "l:x:y:w:h:vp", long_options,
                        &option_index)) != -1)
                switch (i) {
                        case 'l':
                                loop_count = atoi(optarg);
                                break;
                        case 'x':
                                x = atoi(optarg);
                                break;
                        case 'y':
                                y = atoi(optarg);
                                break;
                        case 'w':
                                width = atoi(optarg);
                                break;
                        case 'h':
                                height = atoi(optarg);
                                break;
                        case 'v':
                                verbose = 1;
                                break;
                        case 'p':
                                PrintUsage();
                                return 0;
                        case '?':
                                printf("unknown option `\\x%x`.\n", optopt);
                                return 1;
                        default:
                                goto done;
                }

        failure = XInitialize(x, y, width, height);
        if (failure)
                goto done;

        failure = EglInitialize();
        if (failure)
                goto clean_x;

        InitGraphicsState();

        printf("Test started, window (x,y,w,h) = (%d,%d,%d,%d), pid = %d.\n",
                x, y, width, height, getpid());
        if (verbose)
                printf("Looping for %d iterations.\n", loop_count);

        for(i = 0; i < loop_count; i++) {
            int j;
            for(j = 0 ; j < 3 ; j++) {
                failure |= RunTest(width, height);
            }
            eglSwapBuffers(egl_display, egl_surface);
        }

        if (!failure) {
                err_code = glGetError();
                if (err_code == GL_NO_ERROR)
                        failure = false;
                else {
                        printf("GL Error Occured : %d\n", err_code);
                        failure = 1;
                }
        }

        CleanupEgl();
clean_x:
        CleanupX();

done:
        printf("Test completed [%s]: pid = %d\n",
                (failure ? "FAIL" : "SUCCESS"), getpid());
        return failure ? -1 : 0;
}

