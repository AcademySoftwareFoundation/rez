#include <stdio.h>

#define PROJECT_NAME "simple"

int main(int argc, char **argv) {
    if (argc != 1) {
        printf("%s takes no arguments.\n", argv[0]);
        return 1;
    }
    printf("This is project %s.\n", PROJECT_NAME);
    return 0;
}
