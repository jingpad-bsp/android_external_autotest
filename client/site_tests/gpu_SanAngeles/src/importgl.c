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
 * $Id: importgl.c,v 1.4 2005/02/08 18:42:55 tonic Exp $
 * $Revision: 1.4 $
 */

#include <stdlib.h>
#include <dlfcn.h>
static void *sGLESSO = NULL;

#define IMPORTGL_NO_FNPTR_DEFS
#define IMPORTGL_API
#define IMPORTGL_FNPTRINIT = NULL
#include "importgl.h"


/* Imports function pointers to selected function calls in OpenGL ES Common
 * or Common Lite profile DLL or shared object. The function pointers are
 * stored as global symbols with equivalent function name but prefixed with
 * "funcPtr_". Standard gl/egl calls are redirected to the function pointers
 * with preprocessor macros (see importgl.h).
 */
int importGLInit()
{
    int result = 1;

#undef IMPORT_FUNC

    sGLESSO = dlopen("libGLES_CM.so", RTLD_NOW);
    if (sGLESSO == NULL)
        sGLESSO = dlopen("libGLES_CL.so", RTLD_NOW);
    if (sGLESSO == NULL)
        return 0;   // Cannot find OpenGL ES Common or Common Lite SO.

#define IMPORT_FUNC(funcName) do { \
        void *procAddress = (void *)dlsym(sGLESSO, #funcName); \
        if (procAddress == NULL) result = 0; \
        *((void **)&FNPTR(funcName)) = procAddress; } while (0)

    IMPORT_FUNC(eglChooseConfig);
    IMPORT_FUNC(eglCreateContext);
    IMPORT_FUNC(eglCreateWindowSurface);
    IMPORT_FUNC(eglDestroyContext);
    IMPORT_FUNC(eglDestroySurface);
    IMPORT_FUNC(eglGetConfigAttrib);
    IMPORT_FUNC(eglGetConfigs);
    IMPORT_FUNC(eglGetDisplay);
    IMPORT_FUNC(eglGetError);
    IMPORT_FUNC(eglInitialize);
    IMPORT_FUNC(eglMakeCurrent);
    IMPORT_FUNC(eglSwapBuffers);
    IMPORT_FUNC(eglTerminate);

    IMPORT_FUNC(glBlendFunc);
    IMPORT_FUNC(glClear);
    IMPORT_FUNC(glClearColorx);
    IMPORT_FUNC(glColor4x);
    IMPORT_FUNC(glColorPointer);
    IMPORT_FUNC(glDisable);
    IMPORT_FUNC(glDisableClientState);
    IMPORT_FUNC(glDrawArrays);
    IMPORT_FUNC(glEnable);
    IMPORT_FUNC(glEnableClientState);
    IMPORT_FUNC(glFrustumx);
    IMPORT_FUNC(glGetError);
    IMPORT_FUNC(glLightxv);
    IMPORT_FUNC(glLoadIdentity);
    IMPORT_FUNC(glMaterialx);
    IMPORT_FUNC(glMaterialxv);
    IMPORT_FUNC(glMatrixMode);
    IMPORT_FUNC(glMultMatrixx);
    IMPORT_FUNC(glNormalPointer);
    IMPORT_FUNC(glPopMatrix);
    IMPORT_FUNC(glPushMatrix);
    IMPORT_FUNC(glRotatex);
    IMPORT_FUNC(glScalex);
    IMPORT_FUNC(glShadeModel);
    IMPORT_FUNC(glTranslatex);
    IMPORT_FUNC(glVertexPointer);
    IMPORT_FUNC(glViewport);

    return result;
}


void importGLDeinit()
{
    dlclose(sGLESSO);
}
