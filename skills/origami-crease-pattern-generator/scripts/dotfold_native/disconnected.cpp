// Expose the two in-process stages of the upstream Windows driver.
// Python runs the intervening executables in a private working directory.
#define main upstream_disconnected_main
#include "solve_non_connect.cpp"
#undef main

int main(int argc, char **argv) {
    if (argc == 3 && std::string(argv[1]) == "edges") {
        BoundaryExtractor::save_as_edges(argv[2], "edges.txt");
        return 0;
    }
    if (argc == 2 && std::string(argv[1]) == "tiles") {
        std::string candidate, corners;
        searchCP(generate_fold_assignments("filtered_solutions.txt"), candidate, corners);
        std::cout << "CPSTR:" << candidate << "\nCORNERS:" << corners << "\n";
        return 0;
    }
    return 2;
}
