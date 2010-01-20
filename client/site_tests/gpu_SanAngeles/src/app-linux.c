/* San Angeles Observation OpenGL ES version example
 * Copyright 2004-2005 Jetro Lauha
 * All rights reserved.
 * Web: http://iki.fi/jetro/
 *
 * This source is free software; you can redistribute it and/or
 * modify it under the terms of EITHER:
 *   (1) The GNU Lesser General Public License as published by the Free
 *       Software Foundation; either version 2.1 of the License, or (at
 *       your option) any later version. The text of the GNU Lesser
 *       General Public License is included with this source in the
 *       file LICENSE-LGPL.txt.
 *   (2) The BSD-style license that is included with this source in
 *       the file LICENSE-BSD.txt.
 *
 * This source is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the files
 * LICENSE-LGPL.txt and LICENSE-BSD.txt for more details.
 *
 * $Id: app-linux.c,v 1.4 2005/02/08 18:42:48 tonic Exp $
 * $Revision: 1.4 $
 *
 * Parts of this source file is based on test/example code from
 * GLESonGL implementation by David Blythe. Here is copy of the
 * license notice from that source:
 *
 * Copyright (C) 2003  David Blythe   All Rights Reserved.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included
 * in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 * OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
 * DAVID BLYTHE BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
 * AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

// With regular OpenGL (instead of GLES), we use glx library functions to
// initialize and finalyze.

#include <stdlib.h>
#include <stdio.h>
#include <sys/time.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>

#include "importgl.h"

#include "app.h"


int gAppAlive = 1;
static Display *sDisplay;
static Window sWindow;
static int sWindowWidth = WINDOW_DEFAULT_WIDTH;
static int sWindowHeight = WINDOW_DEFAULT_HEIGHT;
#ifdef SAN_ANGELES_OBSERVATION_GLES
static const char sAppName[] =
    "San Angeles Observation OpenGL ES version example (Linux)";
static EGLDisplay sEglDisplay = EGL_NO_DISPLAY;
static EGLConfig sEglConfig;
static EGLContext sEglContext = EGL_NO_CONTEXT;
static EGLSurface sEglSurface = EGL_NO_SURFACE;
#else  // !SAN_ANGELES_OBSERVATION_GLES
static const char sAppName[] =
    "San Angeles Observation OpenGL version example (Linux)";
static GLXContext sContext;
#endif  // SAN_ANGELES_OBSERVATION_GLES | !SAN_ANGELES_OBSERVATION_GLES

static void checkGLErrors()
{
    GLenum error = glGetError();
    if (error != GL_NO_ERROR)
        fprintf(stderr, "GL Error: 0x%04x\n", (int)error);
}

#ifdef SAN_ANGELES_OBSERVATION_GLES

static void checkEGLErrors()
{
    EGLint error = eglGetError();
    // GLESonGL seems to be returning 0 when there is no errors?
    if (error && error != EGL_SUCCESS)
        fprintf(stderr, "EGL Error: 0x%04x\n", (int)error);
}

// Initializes and opens both X11 display and OpenGL ES.
static int initGraphics()
{
    static const EGLint configAttribs[] =
    {
#if (WINDOW_BPP == 16)
        EGL_RED_SIZE,       5,
        EGL_GREEN_SIZE,     5,
        EGL_BLUE_SIZE,      5,
#elif (WINDOW_BPP == 32)
        EGL_RED_SIZE,       8,
        EGL_GREEN_SIZE,     8,
        EGL_BLUE_SIZE,      8,
#else
#error WINDOW_BPP must be 16 or 32
#endif
        EGL_DEPTH_SIZE,     16,
        EGL_ALPHA_SIZE,     EGL_DONT_CARE,
        EGL_STENCIL_SIZE,   EGL_DONT_CARE,
        EGL_SURFACE_TYPE,   EGL_WINDOW_BIT,
        EGL_NONE
    };
    EGLBoolean success;
    EGLint numConfigs;
    EGLint majorVersion;
    EGLint minorVersion;

    int importGLResult;
    importGLResult = importGLInit();
    if (!importGLResult)
        return 0;

    sDisplay = XOpenDisplay(NULL);

    sEglDisplay = eglGetDisplay(sDisplay);
    success = eglInitialize(sEglDisplay, &majorVersion, &minorVersion);
    if (success != EGL_FALSE)
        success = eglGetConfigs(sEglDisplay, NULL, 0, &numConfigs);
    if (success != EGL_FALSE)
        success = eglChooseConfig(sEglDisplay, configAttribs,
                                  &sEglConfig, 1, &numConfigs);
    if (success != EGL_FALSE)
    {
        sEglContext = eglCreateContext(sEglDisplay, sEglConfig, NULL, NULL);
        if (sEglContext == EGL_NO_CONTEXT)
            success = EGL_FALSE;
    }
    if (success != EGL_FALSE)
    {
        XSetWindowAttributes swa;
        XVisualInfo *vi, tmp;
        XSizeHints sh;
        int n;
        EGLint vid;

        eglGetConfigAttrib(sEglDisplay, sEglConfig,
                           EGL_NATIVE_VISUAL_ID, &vid);
        tmp.visualid = vid;
        vi = XGetVisualInfo(sDisplay, VisualIDMask, &tmp, &n);
        swa.colormap = XCreateColormap(sDisplay,
                                       RootWindow(sDisplay, vi->screen),
                                       vi->visual, AllocNone);
        sh.flags = PMinSize | PMaxSize;
        sh.min_width = sh.max_width = sWindowWidth;
        sh.min_height = sh.max_height = sWindowHeight;
        swa.border_pixel = 0;
        swa.event_mask = ExposureMask | StructureNotifyMask |
                         KeyPressMask | ButtonPressMask | ButtonReleaseMask;
        sWindow = XCreateWindow(sDisplay, RootWindow(sDisplay, vi->screen),
                                0, 0, sWindowWidth, sWindowHeight,
                                0, vi->depth, InputOutput, vi->visual,
                                CWBorderPixel | CWColormap | CWEventMask,
                                &swa);
        XMapWindow(sDisplay, sWindow);
        XSetStandardProperties(sDisplay, sWindow, sAppName, sAppName,
                               None, (void *)0, 0, &sh);
        XFree(vi);
    }
    if (success != EGL_FALSE)
    {
        sEglSurface = eglCreateWindowSurface(sEglDisplay, sEglConfig,
                                             (NativeWindowType)sWindow, NULL);
        if (sEglSurface == EGL_NO_SURFACE)
            success = EGL_FALSE;
    }
    if (success != EGL_FALSE)
        success = eglMakeCurrent(sEglDisplay, sEglSurface,
                                 sEglSurface, sEglContext);

    if (success == EGL_FALSE)
        checkEGLErrors();

    return success != EGL_FALSE;
}

static void deinitGraphics()
{
    eglMakeCurrent(sEglDisplay, NULL, NULL, NULL);
    eglDestroyContext(sEglDisplay, sEglContext);
    eglDestroySurface(sEglDisplay, sEglSurface);
    eglTerminate(sEglDisplay);
    importGLDeinit();
}

#else  // !SAN_ANGELES_OBSERVATION_GLES

// Initializes and opens both X11 display and OpenGL.
static int initGraphics()
{
    sDisplay = XOpenDisplay(NULL);
    if(sDisplay == NULL)
    {
        fprintf(stderr, "XOpenDisplay failed\n");
        return 0;
    }
    Window root_window = DefaultRootWindow(sDisplay);
    GLint att[] = { GLX_RGBA,
                    GLX_DEPTH_SIZE,
                    24,
                    GLX_DOUBLEBUFFER,
                    None };
    XVisualInfo *vi = glXChooseVisual(sDisplay, 0, att);
    if (vi == NULL)
    {
        fprintf(stderr, "glXChooseVisual failed\n");
        return 0;
    }

    XSetWindowAttributes swa;
    swa.colormap = XCreateColormap(sDisplay,
                                   root_window,
                                   vi->visual,
                                   AllocNone);
    XSizeHints sh;
    sh.flags = PMinSize | PMaxSize;
    sh.min_width = sh.max_width = sWindowWidth;
    sh.min_height = sh.max_height = sWindowHeight;
    swa.border_pixel = 0;
    swa.event_mask = ExposureMask | StructureNotifyMask |
                     KeyPressMask | ButtonPressMask | ButtonReleaseMask;
    sWindow = XCreateWindow(sDisplay, root_window,
                            0, 0, sWindowWidth, sWindowHeight,
                            0, vi->depth, InputOutput, vi->visual,
                            CWBorderPixel | CWColormap | CWEventMask,
                            &swa);
    XMapWindow(sDisplay, sWindow);
    XSetStandardProperties(sDisplay, sWindow, sAppName, sAppName,
                           None, (void *)0, 0, &sh);

    sContext = glXCreateContext(sDisplay, vi, NULL, GL_TRUE);
    glXMakeCurrent(sDisplay, sWindow, sContext);

    glEnable(GL_DEPTH_TEST);

    XFree(vi);
    return 1;
}

static void deinitGraphics()
{
    glXMakeCurrent(sDisplay, None, NULL);
    glXDestroyContext(sDisplay, sContext);
    XDestroyWindow(sDisplay, sWindow);
    XCloseDisplay(sDisplay);
}

#endif  // SAN_ANGELES_OBSERVATION_GLES | !SAN_ANGELES_OBSERVATION_GLES

int main(int argc, char *argv[])
{
    // not referenced:
    argc = argc;
    argv = argv;

    if (!initGraphics())
    {
        fprintf(stderr, "Graphics initialization failed.\n");
        return EXIT_FAILURE;
    }

    appInit();

    double total_time = 0.0;
    int num_frames = 0;

    while (gAppAlive)
    {
        while (XPending(sDisplay))
        {
            XEvent ev;
            XNextEvent(sDisplay, &ev);
            switch (ev.type)
            {
            case KeyPress:
                {
                    unsigned int keycode, keysym;
                    keycode = ((XKeyEvent *)&ev)->keycode;
                    keysym = XKeycodeToKeysym(sDisplay, keycode, 0);
                    if (keysym == XK_Return || keysym == XK_Escape)
                        gAppAlive = 0;
                }
                break;
            }
        }

        if (gAppAlive)
        {
            struct timeval timeNow, timeAfter;

            gettimeofday(&timeNow, NULL);
            appRender(timeNow.tv_sec * 1000 + timeNow.tv_usec / 1000,
                      sWindowWidth, sWindowHeight);
            gettimeofday(&timeAfter, NULL);
#ifdef SAN_ANGELES_OBSERVATION_GLES
            checkGLErrors();
            eglSwapBuffers(sEglDisplay, sEglSurface);
            checkEGLErrors();
#else  // !SAN_ANGELES_OBSERVATION_GLES
            glXSwapBuffers(sDisplay, sWindow);
            checkGLErrors();
#endif  // SAN_ANGELES_OBSERVATION_GLES | !SAN_ANGELES_OBSERVATION_GLES
            total_time += (timeAfter.tv_sec - timeNow.tv_sec) +
                          (timeAfter.tv_usec - timeNow.tv_usec) / 1000000.0;
            num_frames++;
        }
    }

    appDeinit();
    deinitGraphics();

    fprintf(stdout, "frame_rate = %.1f\n", num_frames / total_time);

    return EXIT_SUCCESS;
}

