#include <algorithm>
#include <atomic>
//#include <ctime>
#include <future>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;

struct Edge {
  int32_t from, to;
};
using Loop = vector<int32_t>;

struct Helper {
  explicit Helper(const vector<Edge> &edges) {
    // build adj
    for (const auto &e : edges) {
      adj1[e.from].push_back(e.to);
      adj2[e.to].push_back(e.from);
    }
    for (auto &p : adj1) {
      sort(p.second.begin(), p.second.end());
    }
    for (auto &p : adj2) {
      sort(p.second.begin(), p.second.end());
    }
    for (const auto &p : adj1) {
      id.push_back(p.first);
    }

    compute();

    // sort results
    sort(result.begin(), result.end(),
         [](const Loop &l, const Loop &r) { return compare(l, r) < 0; });
  }

  const vector<Loop> &getResult() const { return result; }

private:
  vector<Loop> doCompute(int32_t beg, int32_t end) {
    unordered_map<int32_t, bool> visited;
    unordered_map<int32_t, bool> marked;

    vector<int32_t> st;
    vector<Loop> loops;

    for (int32_t i = beg; i != end; ++i) {
      auto n = id[i];
      marked.clear();
      dfs1(visited, marked, n, n, 0);
      dfs2(visited, marked, st, n, n, loops);
    }

    return move(loops);
  };

  void compute() {
    const int32_t THREAD = 4;

    vector<future<vector<Loop>>> futures;
    const int32_t TILE = int32_t(id.size()) / (THREAD * 10);

    atomic<int32_t> off{0};

    futures.reserve(THREAD);
    for (int32_t i = 0; i < THREAD; ++i) {
      futures.emplace_back(async(launch::async, [this, &off, TILE] {
        unordered_map<int32_t, bool> visited;
        unordered_map<int32_t, bool> marked;

        vector<int32_t> st;
        vector<Loop> loops;

        const auto alloc_task = [&off, TILE, this](int32_t &beg,
                                                   int32_t &end) -> bool {
          beg = off.load();
          do {
            end = beg + TILE;
          } while (!off.compare_exchange_weak(beg, end));

          end = min<int32_t>(end, int32_t(id.size()));

          return beg < int32_t(id.size());
        };

        int32_t beg, end;
        while (alloc_task(beg, end)) {
          for (int32_t i = beg; i != end; ++i) {
            int32_t n = id[i];

            marked.clear();

            dfs1(visited, marked, n, n, 0);
            dfs2(visited, marked, st, n, n, loops);
          }
        }

        return move(loops);
      }));
    }

    for (auto &f : futures) {
      for (auto &l : f.get()) {
        result.emplace_back(move(l));
      }
    }
  }

  void dfs1(unordered_map<int32_t, bool> &visited,
            unordered_map<int32_t, bool> &marked, int32_t start, int32_t cur,
            int32_t depth) const {
    if (visited[cur] || adj2.find(cur) == adj2.end() || depth > 3) {
      return;
    }

    visited[cur] = true;

    const auto &v = adj2.at(cur);

    marked[cur] = true; // mark node

    auto upper = upper_bound(v.begin(), v.end(), start);
    for (auto it = upper; it != v.end(); ++it) {
      dfs1(visited, marked, start, *it, depth + 1);
    }

    visited[cur] = false;
  }

  void dfs2(unordered_map<int32_t, bool> &visited,
            unordered_map<int32_t, bool> &marked, vector<int32_t> &st,
            int32_t start, int32_t cur, vector<Loop> &output) const {
    if (visited[cur] || adj1.find(cur) == adj2.end()) {
      return;
    }

    visited[cur] = true;
    st.push_back(cur);

    const auto &v = adj1.at(cur);
    if (st.size() >= 3 && contains(v, start)) {
      output.push_back(st);
    }

    if (st.size() <= 4 || (st.size() <= 6 && marked[cur])) {
      auto upper = upper_bound(v.begin(), v.end(), start);
      for (auto it = upper; it != v.end(); ++it) {
        dfs2(visited, marked, st, start, *it, output);
      }
    }

    visited[cur] = false;
    st.pop_back();
  }

  static inline int compare(const Loop &l, const Loop &r) {
    if (l.size() != r.size()) {
      return int(l.size()) - int(r.size());
    }

    const int L = int(l.size());
    for (int p = 0; p < L; ++p) {
      if (l[p] != r[p]) {
        return l[p] - r[p];
      }
    }

    return 0;
  }

  static inline bool contains(const vector<int32_t> &v, int32_t target) {
    return find(v.begin(), v.end(), target) != v.end();
  }

  vector<int32_t> id;
  unordered_map<int32_t, vector<int32_t>> adj1;
  unordered_map<int32_t, vector<int32_t>> adj2;
  vector<Loop> result;
};

vector<Edge> loadEdges(const char *f) {
  vector<Edge> edges;
  FILE *fp = fopen(f, "r");

  int from, to, val;
  while (fscanf(fp, "%d, %d,%d", &from, &to, &val) == 3) {
    edges.push_back({from, to});
  }

  fclose(fp);

  return move(edges);
}

void saveLoops(const char *f, const vector<Loop> &loops) {
  FILE *fp = fopen(f, "w");
  fprintf(fp, "%d\n", int(loops.size()));

  for (const auto &l : loops) {
    for (size_t i = 0; i < l.size(); ++i) {
      fprintf(fp, "%d", l[i]);
      if (i + 1 != l.size()) {
        fprintf(fp, ",");
      }
    }
    fprintf(fp, "\n");
  }
  fclose(fp);
}

int main() {
  //auto t1 = clock();

  auto edges = loadEdges("/data/test_data.txt");
  Helper helper(edges);
  saveLoops("/projects/student/result.txt", helper.getResult());

  //auto t2 = clock();
  //printf("input edges: %d\n", int(edges.size()));
  //printf("loops count: %d\n", int(helper.getResult().size()));
  //printf("total time: %f\n", float(t2 - t1) / float(CLOCKS_PER_SEC));
}
