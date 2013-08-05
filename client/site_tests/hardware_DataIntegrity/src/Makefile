DIR     = .
TARGET  = "${DIR}/datint"

CC     ?= gcc
WFLAGS  = -W -Wall -Wextra -Werror
LFLAGS  =
CFLAGS  = -c -O2 -ansi $(WFLAGS)
LIBS    =

HDRS := $(wildcard *.h)
SRCS := $(wildcard *.c)
OBJS = $(SRCS:.c=.o)

.PHONY: all clean build rebuild

all: build

$(TARGET): $(OBJS)
	$(CC) $^ $(LIBS) -o $@

clean:
	rm -f $(OBJS) $(TARGET)

build: $(TARGET)

rebuild: clean build
