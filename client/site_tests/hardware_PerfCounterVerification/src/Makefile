CFLAGS=-O0 -g

OUTPUTS=noploop noploop_branch.txt

all: $(OUTPUTS)

noploop: noploop.c

noploop_branch.txt: noploop
	./find_loop_instructions.py $< > $@

clean:
	rm -rf $(OUTPUTS)
