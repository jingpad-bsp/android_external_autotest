// Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// We mock the x-postfix GLES functions here using regular OpenGL functions.
// In general, we translate the GLfixed and GLclampx values to GLfloat, and
// call the corresponding f-postfix functions.

#include "importgl.h"

static GLfloat fixed2float(GLfixed num)
{
    return num / 65536.f;
}

static GLclampf fixed2float_clamp(GLclampx num)
{
    return num / 65536.f;
}

void glScalex(GLfixed x, GLfixed y, GLfixed z)
{
    glScalef(fixed2float(x),
             fixed2float(y),
             fixed2float(z));
}

void glTranslatex(GLfixed x, GLfixed y, GLfixed z)
{
    glTranslatef(fixed2float(x),
                 fixed2float(y),
                 fixed2float(z));
}

void glRotatex(GLfixed angle, GLfixed x, GLfixed y, GLfixed z)
{
    glRotatef(fixed2float(angle),
              fixed2float(x),
              fixed2float(y),
              fixed2float(z));
}

void glColor4x(GLfixed r, GLfixed g, GLfixed b, GLfixed a)
{
    glColor4f(fixed2float(r),
              fixed2float(g),
              fixed2float(b),
              fixed2float(a));
}

void glClearColorx(GLclampx red, GLclampx green, GLclampx blue, GLclampx alpha)
{
    glClearColor(fixed2float_clamp(red),
                 fixed2float_clamp(green),
                 fixed2float_clamp(blue),
                 fixed2float_clamp(alpha));
}

void glLightxv(GLenum light, GLenum pname, GLfixed* params)
{
    GLfloat fparams[4];
    int i;
    for (i = 0; i < 4; ++i)
        fparams[i] = fixed2float(params[i]);
    glLightfv(light, pname, fparams);
}

void glMaterialx(GLenum face, GLenum pname, GLfixed param)
{
    glMaterialf(face,
                pname,
                fixed2float(param));
}

void glMaterialxv(GLenum face, GLenum pname, GLfixed* params)
{
    GLfloat fparams[4];
    int i;
    for (i = 0; i < 4; ++i)
        fparams[i] = fixed2float(params[i]);
    glMaterialfv(face, pname, fparams);
}

void glFrustumx(GLfixed l, GLfixed r, GLfixed b,
                GLfixed t, GLfixed n, GLfixed f)
{
    glFrustum(fixed2float(l), fixed2float(r), fixed2float(b),
              fixed2float(t), fixed2float(n), fixed2float(f));
}

void glMultMatrixx(const GLfixed m[16])
{
    GLfloat fm[16];
    int i;
    for (i = 0; i < 16; ++i)
        fm[i] = fixed2float(m[i]);
    glMultMatrixf(fm);
}
