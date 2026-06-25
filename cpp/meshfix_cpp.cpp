#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace fs = std::filesystem;

struct Vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

using Face = std::array<int, 3>;
using Edge = std::pair<int, int>;

struct Mesh {
    std::vector<Vec3> vertices;
    std::vector<Face> faces;
    fs::path source;
};

struct TriangleQuality {
    double area = 0.0;
    double min_angle = 0.0;
    double max_angle = 0.0;
    double aspect_ratio = 0.0;
    double shortest_edge = 0.0;
    double longest_edge = 0.0;
};

struct MeshQualitySummary {
    std::string name;
    std::size_t vertex_count = 0;
    std::size_t face_count = 0;
    double min_angle = 0.0;
    double avg_min_angle = 0.0;
    double max_angle = 0.0;
    double avg_aspect_ratio = 0.0;
    int low_aspect_count = 0;
    int needle_like_count = 0;
    int cap_like_count = 0;
    int near_zero_area_count = 0;
    int bad_triangle_count = 0;
};

struct TopologySummary {
    std::string name;
    std::size_t vertex_count = 0;
    std::size_t face_count = 0;
    std::size_t edge_count = 0;
    int boundary_edge_count = 0;
    int nonmanifold_edge_count = 0;
    long long euler_characteristic = 0;
};

struct CleanupIterationStats {
    int iteration = 0;
    int bad_before = 0;
    int collapse_edges = 0;
    int split_edges = 0;
    int collapses = 0;
    int splits = 0;
    std::size_t vertices = 0;
    std::size_t faces = 0;
};

struct CleanupResult {
    Mesh mesh;
    std::vector<CleanupIterationStats> stats;
};

struct QualityOptions {
    double needle_angle_deg = 5.0;
    double cap_angle_deg = 175.0;
    double aspect_threshold = 0.05;
    double area_epsilon_factor = 1e-14;
};

Vec3 add(const Vec3& a, const Vec3& b) {
    return {a.x + b.x, a.y + b.y, a.z + b.z};
}

Vec3 sub(const Vec3& a, const Vec3& b) {
    return {a.x - b.x, a.y - b.y, a.z - b.z};
}

Vec3 mul(const Vec3& a, double scalar) {
    return {a.x * scalar, a.y * scalar, a.z * scalar};
}

double dot(const Vec3& a, const Vec3& b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

Vec3 cross(const Vec3& a, const Vec3& b) {
    return {
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    };
}

double norm(const Vec3& a) {
    return std::sqrt(dot(a, a));
}

double distance(const Vec3& a, const Vec3& b) {
    return norm(sub(a, b));
}

Vec3 midpoint(const Vec3& a, const Vec3& b) {
    return mul(add(a, b), 0.5);
}

Edge edge_key(int a, int b) {
    return a < b ? Edge{a, b} : Edge{b, a};
}

std::array<Edge, 3> face_edges(const Face& face) {
    return {
        edge_key(face[0], face[1]),
        edge_key(face[1], face[2]),
        edge_key(face[2], face[0]),
    };
}

std::string strip_comment(const std::string& line) {
    const std::size_t pos = line.find('#');
    return pos == std::string::npos ? line : line.substr(0, pos);
}

std::vector<std::string> read_tokens(const fs::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("Cannot open " + path.string());
    }

    std::vector<std::string> tokens;
    std::string line;
    while (std::getline(input, line)) {
        std::istringstream stream(strip_comment(line));
        std::string token;
        while (stream >> token) {
            tokens.push_back(token);
        }
    }
    return tokens;
}

Mesh read_off(const fs::path& path) {
    const std::vector<std::string> tokens = read_tokens(path);
    if (tokens.empty() || tokens[0] != "OFF") {
        throw std::runtime_error(path.string() + " is not an OFF file");
    }
    if (tokens.size() < 4) {
        throw std::runtime_error(path.string() + " has an incomplete OFF header");
    }

    std::size_t cursor = 1;
    const int vertex_count = std::stoi(tokens[cursor++]);
    const int face_count = std::stoi(tokens[cursor++]);
    cursor++; // OFF edge count, unused.

    Mesh mesh;
    mesh.source = path;
    mesh.vertices.reserve(static_cast<std::size_t>(vertex_count));
    mesh.faces.reserve(static_cast<std::size_t>(face_count));

    for (int i = 0; i < vertex_count; ++i) {
        if (cursor + 2 >= tokens.size()) {
            throw std::runtime_error(path.string() + " ended while reading vertices");
        }
        Vec3 v;
        v.x = std::stod(tokens[cursor++]);
        v.y = std::stod(tokens[cursor++]);
        v.z = std::stod(tokens[cursor++]);
        mesh.vertices.push_back(v);
    }

    for (int i = 0; i < face_count; ++i) {
        if (cursor >= tokens.size()) {
            throw std::runtime_error(path.string() + " ended while reading faces");
        }
        const int degree = std::stoi(tokens[cursor++]);
        if (cursor + static_cast<std::size_t>(degree) > tokens.size()) {
            throw std::runtime_error(path.string() + " has an incomplete face");
        }
        std::vector<int> indices;
        indices.reserve(static_cast<std::size_t>(degree));
        for (int j = 0; j < degree; ++j) {
            indices.push_back(std::stoi(tokens[cursor++]));
        }
        if (degree < 3) {
            continue;
        }
        for (int j = 1; j < degree - 1; ++j) {
            mesh.faces.push_back({indices[0], indices[j], indices[j + 1]});
        }
    }

    return mesh;
}

void write_off(const Mesh& mesh, const fs::path& path) {
    if (path.has_parent_path()) {
        fs::create_directories(path.parent_path());
    }
    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("Cannot write " + path.string());
    }
    output << "OFF\n";
    output << mesh.vertices.size() << " " << mesh.faces.size() << " 0\n";
    output << std::setprecision(12);
    for (const Vec3& v : mesh.vertices) {
        output << v.x << " " << v.y << " " << v.z << "\n";
    }
    for (const Face& f : mesh.faces) {
        output << "3 " << f[0] << " " << f[1] << " " << f[2] << "\n";
    }
}

double safe_angle(const Vec3& a, const Vec3& b, const Vec3& c) {
    constexpr double pi = 3.141592653589793238462643383279502884;
    const Vec3 first = sub(a, b);
    const Vec3 second = sub(c, b);
    const double denom = norm(first) * norm(second);
    if (denom == 0.0) {
        return 0.0;
    }
    const double cosine = std::max(-1.0, std::min(1.0, dot(first, second) / denom));
    return std::acos(cosine) * 180.0 / pi;
}

double triangle_area(const std::vector<Vec3>& vertices, const Face& face) {
    const Vec3& a = vertices[static_cast<std::size_t>(face[0])];
    const Vec3& b = vertices[static_cast<std::size_t>(face[1])];
    const Vec3& c = vertices[static_cast<std::size_t>(face[2])];
    return 0.5 * norm(cross(sub(b, a), sub(c, a)));
}

double bbox_diagonal(const std::vector<Vec3>& vertices) {
    if (vertices.empty()) {
        return 0.0;
    }

    double min_x = vertices[0].x;
    double max_x = vertices[0].x;
    double min_y = vertices[0].y;
    double max_y = vertices[0].y;
    double min_z = vertices[0].z;
    double max_z = vertices[0].z;

    for (const Vec3& v : vertices) {
        min_x = std::min(min_x, v.x);
        max_x = std::max(max_x, v.x);
        min_y = std::min(min_y, v.y);
        max_y = std::max(max_y, v.y);
        min_z = std::min(min_z, v.z);
        max_z = std::max(max_z, v.z);
    }

    return norm({max_x - min_x, max_y - min_y, max_z - min_z});
}

double area_epsilon(const std::vector<Vec3>& vertices) {
    const double diagonal = bbox_diagonal(vertices);
    return std::max(1e-14, diagonal * diagonal * 1e-14);
}

TriangleQuality triangle_quality(const Mesh& mesh, const Face& face) {
    const Vec3& a = mesh.vertices[static_cast<std::size_t>(face[0])];
    const Vec3& b = mesh.vertices[static_cast<std::size_t>(face[1])];
    const Vec3& c = mesh.vertices[static_cast<std::size_t>(face[2])];

    const double ab = distance(a, b);
    const double bc = distance(b, c);
    const double ca = distance(c, a);
    const double shortest = std::min({ab, bc, ca});
    const double longest = std::max({ab, bc, ca});
    const double aspect = longest == 0.0 ? 0.0 : shortest / longest;

    const double angle_a = safe_angle(b, a, c);
    const double angle_b = safe_angle(a, b, c);
    const double angle_c = safe_angle(a, c, b);

    return {
        triangle_area(mesh.vertices, face),
        std::min({angle_a, angle_b, angle_c}),
        std::max({angle_a, angle_b, angle_c}),
        aspect,
        shortest,
        longest,
    };
}

std::string mesh_name(const Mesh& mesh) {
    if (mesh.source.empty()) {
        return "<memory>";
    }
    return mesh.source.filename().string();
}

MeshQualitySummary analyze_mesh(const Mesh& mesh, const QualityOptions& options) {
    MeshQualitySummary summary;
    summary.name = mesh_name(mesh);
    summary.vertex_count = mesh.vertices.size();
    summary.face_count = mesh.faces.size();

    if (mesh.faces.empty()) {
        return summary;
    }

    summary.min_angle = std::numeric_limits<double>::infinity();
    summary.max_angle = -std::numeric_limits<double>::infinity();
    const double epsilon = std::max(
        options.area_epsilon_factor,
        bbox_diagonal(mesh.vertices) * bbox_diagonal(mesh.vertices) * options.area_epsilon_factor
    );

    double min_angle_sum = 0.0;
    double aspect_sum = 0.0;

    for (const Face& face : mesh.faces) {
        const TriangleQuality q = triangle_quality(mesh, face);
        summary.min_angle = std::min(summary.min_angle, q.min_angle);
        summary.max_angle = std::max(summary.max_angle, q.max_angle);
        min_angle_sum += q.min_angle;
        aspect_sum += q.aspect_ratio;

        const bool low_aspect = q.aspect_ratio < options.aspect_threshold;
        const bool needle = q.min_angle < options.needle_angle_deg || low_aspect;
        const bool cap = q.max_angle > options.cap_angle_deg;
        const bool zero_area = q.area <= epsilon;

        summary.low_aspect_count += low_aspect ? 1 : 0;
        summary.needle_like_count += needle ? 1 : 0;
        summary.cap_like_count += cap ? 1 : 0;
        summary.near_zero_area_count += zero_area ? 1 : 0;
        summary.bad_triangle_count += (needle || cap || zero_area) ? 1 : 0;
    }

    summary.avg_min_angle = min_angle_sum / static_cast<double>(mesh.faces.size());
    summary.avg_aspect_ratio = aspect_sum / static_cast<double>(mesh.faces.size());
    return summary;
}

std::map<Edge, std::vector<int>> edge_faces(const std::vector<Face>& faces) {
    std::map<Edge, std::vector<int>> result;
    for (std::size_t i = 0; i < faces.size(); ++i) {
        for (const Edge& edge : face_edges(faces[i])) {
            result[edge].push_back(static_cast<int>(i));
        }
    }
    return result;
}

std::vector<std::set<int>> neighbors(const std::vector<Face>& faces, std::size_t vertex_count) {
    std::vector<std::set<int>> result(vertex_count);
    for (const Face& face : faces) {
        result[static_cast<std::size_t>(face[0])].insert({face[1], face[2]});
        result[static_cast<std::size_t>(face[1])].insert({face[0], face[2]});
        result[static_cast<std::size_t>(face[2])].insert({face[0], face[1]});
    }
    return result;
}

std::set<int> edge_opposites(
    const std::vector<Face>& faces,
    const std::vector<int>& incident_faces,
    const Edge& edge
) {
    std::set<int> result;
    for (int face_index : incident_faces) {
        const Face& face = faces[static_cast<std::size_t>(face_index)];
        for (int vertex : face) {
            if (vertex != edge.first && vertex != edge.second) {
                result.insert(vertex);
            }
        }
    }
    return result;
}

bool same_set(const std::set<int>& a, const std::set<int>& b) {
    return a.size() == b.size() && std::equal(a.begin(), a.end(), b.begin());
}

Mesh cleanup_mesh(const Mesh& mesh) {
    const double epsilon = area_epsilon(mesh.vertices);
    std::vector<Face> clean_faces;
    std::set<Face> seen_faces;

    for (const Face& face : mesh.faces) {
        std::set<int> unique_vertices(face.begin(), face.end());
        if (unique_vertices.size() != 3) {
            continue;
        }
        if (triangle_area(mesh.vertices, face) <= epsilon) {
            continue;
        }
        Face key = face;
        std::sort(key.begin(), key.end());
        if (seen_faces.count(key) != 0) {
            continue;
        }
        seen_faces.insert(key);
        clean_faces.push_back(face);
    }

    std::set<int> used_set;
    for (const Face& face : clean_faces) {
        used_set.insert(face.begin(), face.end());
    }

    std::map<int, int> remap;
    std::vector<Vec3> compact_vertices;
    compact_vertices.reserve(used_set.size());
    int new_index = 0;
    for (int old_index : used_set) {
        remap[old_index] = new_index++;
        compact_vertices.push_back(mesh.vertices[static_cast<std::size_t>(old_index)]);
    }

    std::vector<Face> compact_faces;
    compact_faces.reserve(clean_faces.size());
    for (const Face& face : clean_faces) {
        compact_faces.push_back({remap[face[0]], remap[face[1]], remap[face[2]]});
    }

    return {compact_vertices, compact_faces, mesh.source};
}

Edge longest_edge(const Mesh& mesh, const Face& face) {
    const std::array<Edge, 3> edges = {
        Edge{face[0], face[1]},
        Edge{face[1], face[2]},
        Edge{face[2], face[0]},
    };
    const auto best = std::max_element(edges.begin(), edges.end(), [&](const Edge& lhs, const Edge& rhs) {
        return distance(mesh.vertices[static_cast<std::size_t>(lhs.first)],
                        mesh.vertices[static_cast<std::size_t>(lhs.second)]) <
               distance(mesh.vertices[static_cast<std::size_t>(rhs.first)],
                        mesh.vertices[static_cast<std::size_t>(rhs.second)]);
    });
    return edge_key(best->first, best->second);
}

Edge shortest_edge(const Mesh& mesh, const Face& face) {
    const std::array<Edge, 3> edges = {
        Edge{face[0], face[1]},
        Edge{face[1], face[2]},
        Edge{face[2], face[0]},
    };
    const auto best = std::min_element(edges.begin(), edges.end(), [&](const Edge& lhs, const Edge& rhs) {
        return distance(mesh.vertices[static_cast<std::size_t>(lhs.first)],
                        mesh.vertices[static_cast<std::size_t>(lhs.second)]) <
               distance(mesh.vertices[static_cast<std::size_t>(rhs.first)],
                        mesh.vertices[static_cast<std::size_t>(rhs.second)]);
    });
    return edge_key(best->first, best->second);
}

std::pair<std::set<Edge>, std::set<Edge>> bad_face_operations(
    const Mesh& mesh,
    const QualityOptions& options
) {
    std::set<Edge> collapse_edges;
    std::set<Edge> split_edges;

    for (const Face& face : mesh.faces) {
        const TriangleQuality q = triangle_quality(mesh, face);
        if (q.max_angle > options.cap_angle_deg) {
            split_edges.insert(longest_edge(mesh, face));
        } else if (q.min_angle < options.needle_angle_deg || q.aspect_ratio < options.aspect_threshold) {
            collapse_edges.insert(shortest_edge(mesh, face));
        }
    }

    return {collapse_edges, split_edges};
}

bool collapse_is_safe(
    std::vector<Vec3>& vertices,
    const std::vector<Face>& faces,
    const Edge& edge,
    const Vec3& replacement,
    double epsilon
) {
    const int a = edge.first;
    const int b = edge.second;
    for (const Face& face : faces) {
        const bool contains_a = face[0] == a || face[1] == a || face[2] == a;
        const bool contains_b = face[0] == b || face[1] == b || face[2] == b;
        if (contains_a && contains_b) {
            continue;
        }
        if (!contains_a && !contains_b) {
            continue;
        }

        Face candidate = face;
        for (int& index : candidate) {
            if (index == b) {
                index = a;
            }
        }
        std::set<int> unique_vertices(candidate.begin(), candidate.end());
        if (unique_vertices.size() != 3) {
            return false;
        }

        const Vec3 old_position = vertices[static_cast<std::size_t>(a)];
        vertices[static_cast<std::size_t>(a)] = replacement;
        const double new_area = triangle_area(vertices, candidate);
        vertices[static_cast<std::size_t>(a)] = old_position;
        if (new_area <= epsilon) {
            return false;
        }
    }
    return true;
}

std::pair<Mesh, int> collapse_selected_edges(const Mesh& mesh, const std::set<Edge>& selected_edges) {
    std::vector<Vec3> vertices = mesh.vertices;
    const std::vector<Face> faces = mesh.faces;
    const auto edge_to_faces = edge_faces(faces);
    std::set<Edge> boundary_edges;
    for (const auto& [edge, incident] : edge_to_faces) {
        if (incident.size() == 1) {
            boundary_edges.insert(edge);
        }
    }
    const auto neighbor_sets = neighbors(faces, vertices.size());
    const double epsilon = area_epsilon(vertices);
    std::vector<int> parent(vertices.size());
    std::iota(parent.begin(), parent.end(), 0);
    std::set<int> used;
    int collapses = 0;

    std::vector<std::tuple<double, int, int>> edges;
    for (const Edge& edge : selected_edges) {
        if (edge.first >= 0 && edge.second >= 0 &&
            static_cast<std::size_t>(edge.first) < vertices.size() &&
            static_cast<std::size_t>(edge.second) < vertices.size()) {
            edges.push_back({
                distance(vertices[static_cast<std::size_t>(edge.first)],
                         vertices[static_cast<std::size_t>(edge.second)]),
                edge.first,
                edge.second,
            });
        }
    }
    std::sort(edges.begin(), edges.end());

    for (const auto& [length, a, b] : edges) {
        (void)length;
        const Edge key = edge_key(a, b);
        if (boundary_edges.count(key) != 0) {
            continue;
        }
        const auto incident_it = edge_to_faces.find(key);
        if (incident_it == edge_to_faces.end() || incident_it->second.size() != 2) {
            continue;
        }

        std::set<int> common_neighbors;
        std::set_intersection(
            neighbor_sets[static_cast<std::size_t>(a)].begin(),
            neighbor_sets[static_cast<std::size_t>(a)].end(),
            neighbor_sets[static_cast<std::size_t>(b)].begin(),
            neighbor_sets[static_cast<std::size_t>(b)].end(),
            std::inserter(common_neighbors, common_neighbors.begin())
        );
        if (!same_set(common_neighbors, edge_opposites(faces, incident_it->second, key))) {
            continue;
        }
        if (used.count(a) != 0 || used.count(b) != 0) {
            continue;
        }

        const Vec3 replacement = midpoint(
            vertices[static_cast<std::size_t>(a)],
            vertices[static_cast<std::size_t>(b)]
        );
        if (!collapse_is_safe(vertices, faces, {a, b}, replacement, epsilon)) {
            continue;
        }

        vertices[static_cast<std::size_t>(a)] = replacement;
        parent[static_cast<std::size_t>(b)] = a;
        used.insert(a);
        used.insert(b);
        used.insert(
            neighbor_sets[static_cast<std::size_t>(a)].begin(),
            neighbor_sets[static_cast<std::size_t>(a)].end()
        );
        used.insert(
            neighbor_sets[static_cast<std::size_t>(b)].begin(),
            neighbor_sets[static_cast<std::size_t>(b)].end()
        );
        collapses++;
    }

    if (collapses == 0) {
        return {mesh, 0};
    }

    std::vector<Face> collapsed_faces;
    collapsed_faces.reserve(faces.size());
    for (const Face& face : faces) {
        collapsed_faces.push_back({
            parent[static_cast<std::size_t>(face[0])],
            parent[static_cast<std::size_t>(face[1])],
            parent[static_cast<std::size_t>(face[2])],
        });
    }

    return {cleanup_mesh({vertices, collapsed_faces, mesh.source}), collapses};
}

std::pair<Mesh, int> split_selected_edges(const Mesh& mesh, const std::set<Edge>& split_edges) {
    if (split_edges.empty()) {
        return {mesh, 0};
    }

    std::vector<Vec3> vertices = mesh.vertices;
    std::map<Edge, int> midpoint_indices;
    for (const Edge& edge : split_edges) {
        midpoint_indices[edge] = static_cast<int>(vertices.size());
        vertices.push_back(midpoint(
            vertices[static_cast<std::size_t>(edge.first)],
            vertices[static_cast<std::size_t>(edge.second)]
        ));
    }

    std::vector<Face> new_faces;
    new_faces.reserve(mesh.faces.size() + split_edges.size());

    for (const Face& face : mesh.faces) {
        const int a = face[0];
        const int b = face[1];
        const int c = face[2];
        const Edge edge_ab = edge_key(a, b);
        const Edge edge_bc = edge_key(b, c);
        const Edge edge_ca = edge_key(c, a);
        const bool has_ab = midpoint_indices.count(edge_ab) != 0;
        const bool has_bc = midpoint_indices.count(edge_bc) != 0;
        const bool has_ca = midpoint_indices.count(edge_ca) != 0;
        const int split_count = static_cast<int>(has_ab) + static_cast<int>(has_bc) + static_cast<int>(has_ca);

        if (split_count == 0) {
            new_faces.push_back(face);
            continue;
        }

        const int midpoint_ab = has_ab ? midpoint_indices[edge_ab] : -1;
        const int midpoint_bc = has_bc ? midpoint_indices[edge_bc] : -1;
        const int midpoint_ca = has_ca ? midpoint_indices[edge_ca] : -1;

        if (split_count == 1) {
            if (has_ab) {
                new_faces.push_back({a, midpoint_ab, c});
                new_faces.push_back({midpoint_ab, b, c});
            } else if (has_bc) {
                new_faces.push_back({b, midpoint_bc, a});
                new_faces.push_back({midpoint_bc, c, a});
            } else {
                new_faces.push_back({c, midpoint_ca, b});
                new_faces.push_back({midpoint_ca, a, b});
            }
            continue;
        }

        if (split_count == 2) {
            if (has_ab && has_ca) {
                new_faces.push_back({a, midpoint_ab, midpoint_ca});
                new_faces.push_back({midpoint_ab, b, c});
                new_faces.push_back({midpoint_ab, c, midpoint_ca});
            } else if (has_ab && has_bc) {
                new_faces.push_back({b, midpoint_bc, midpoint_ab});
                new_faces.push_back({midpoint_bc, c, a});
                new_faces.push_back({midpoint_bc, a, midpoint_ab});
            } else {
                new_faces.push_back({c, midpoint_ca, midpoint_bc});
                new_faces.push_back({midpoint_ca, a, b});
                new_faces.push_back({midpoint_ca, b, midpoint_bc});
            }
            continue;
        }

        new_faces.push_back({a, midpoint_ab, midpoint_ca});
        new_faces.push_back({b, midpoint_bc, midpoint_ab});
        new_faces.push_back({c, midpoint_ca, midpoint_bc});
        new_faces.push_back({midpoint_ab, midpoint_bc, midpoint_ca});
    }

    return {cleanup_mesh({vertices, new_faces, mesh.source}), static_cast<int>(split_edges.size())};
}

CleanupResult cleanup_degenerate(Mesh mesh, int iterations, const QualityOptions& options) {
    Mesh current = std::move(mesh);
    std::vector<CleanupIterationStats> stats;

    for (int iteration = 1; iteration <= iterations; ++iteration) {
        const MeshQualitySummary before = analyze_mesh(current, options);
        auto [collapse_edges, split_edges_before] = bad_face_operations(current, options);

        if (collapse_edges.empty() && split_edges_before.empty()) {
            stats.push_back({
                iteration,
                before.bad_triangle_count,
                0,
                0,
                0,
                0,
                current.vertices.size(),
                current.faces.size(),
            });
            break;
        }

        auto [collapsed_mesh, collapses] = collapse_selected_edges(current, collapse_edges);
        current = std::move(collapsed_mesh);
        auto [ignored_collapse_edges, split_edges] = bad_face_operations(current, options);
        (void)ignored_collapse_edges;
        auto [split_mesh, splits] = split_selected_edges(current, split_edges);
        current = std::move(split_mesh);

        stats.push_back({
            iteration,
            before.bad_triangle_count,
            static_cast<int>(collapse_edges.size()),
            static_cast<int>(split_edges.size()),
            collapses,
            splits,
            current.vertices.size(),
            current.faces.size(),
        });
    }

    return {current, stats};
}

TopologySummary analyze_topology(const Mesh& mesh) {
    const auto edge_to_faces = edge_faces(mesh.faces);
    TopologySummary summary;
    summary.name = mesh_name(mesh);
    summary.vertex_count = mesh.vertices.size();
    summary.face_count = mesh.faces.size();
    summary.edge_count = edge_to_faces.size();

    for (const auto& [edge, incident] : edge_to_faces) {
        (void)edge;
        if (incident.size() == 1) {
            summary.boundary_edge_count++;
        }
        if (incident.size() > 2) {
            summary.nonmanifold_edge_count++;
        }
    }

    summary.euler_characteristic = static_cast<long long>(summary.vertex_count)
        - static_cast<long long>(summary.edge_count)
        + static_cast<long long>(summary.face_count);
    return summary;
}

std::vector<fs::path> collect_off_files(const std::vector<std::string>& paths) {
    std::vector<fs::path> files;
    for (const std::string& raw_path : paths) {
        fs::path path(raw_path);
        if (fs::is_directory(path)) {
            for (const auto& entry : fs::recursive_directory_iterator(path)) {
                if (entry.is_regular_file() && entry.path().extension() == ".off") {
                    files.push_back(entry.path());
                }
            }
            std::sort(files.begin(), files.end());
        } else if (fs::is_regular_file(path) && path.extension() == ".off") {
            files.push_back(path);
        } else {
            throw std::runtime_error("No OFF file found at " + path.string());
        }
    }
    return files;
}

std::vector<std::string> csv_row(const MeshQualitySummary& summary) {
    std::ostringstream min_angle;
    std::ostringstream avg_min;
    std::ostringstream max_angle;
    std::ostringstream avg_aspect;
    min_angle << std::fixed << std::setprecision(6) << summary.min_angle;
    avg_min << std::fixed << std::setprecision(6) << summary.avg_min_angle;
    max_angle << std::fixed << std::setprecision(6) << summary.max_angle;
    avg_aspect << std::fixed << std::setprecision(6) << summary.avg_aspect_ratio;
    return {
        summary.name,
        std::to_string(summary.vertex_count),
        std::to_string(summary.face_count),
        min_angle.str(),
        avg_min.str(),
        max_angle.str(),
        avg_aspect.str(),
        std::to_string(summary.low_aspect_count),
        std::to_string(summary.needle_like_count),
        std::to_string(summary.cap_like_count),
        std::to_string(summary.near_zero_area_count),
        std::to_string(summary.bad_triangle_count),
    };
}

void print_quality_table(const std::vector<MeshQualitySummary>& summaries) {
    const std::vector<std::string> headers = {
        "mesh", "V", "F", "min angle", "avg min", "max angle",
        "aspect<.05", "needle-like", "cap-like", "bad"
    };
    std::vector<std::vector<std::string>> rows;
    for (const MeshQualitySummary& s : summaries) {
        std::ostringstream min_angle;
        std::ostringstream avg_min;
        std::ostringstream max_angle;
        min_angle << std::fixed << std::setprecision(2) << s.min_angle;
        avg_min << std::fixed << std::setprecision(2) << s.avg_min_angle;
        max_angle << std::fixed << std::setprecision(2) << s.max_angle;
        rows.push_back({
            s.name,
            std::to_string(s.vertex_count),
            std::to_string(s.face_count),
            min_angle.str(),
            avg_min.str(),
            max_angle.str(),
            std::to_string(s.low_aspect_count),
            std::to_string(s.needle_like_count),
            std::to_string(s.cap_like_count),
            std::to_string(s.bad_triangle_count),
        });
    }

    std::vector<std::size_t> widths(headers.size(), 0);
    for (std::size_t i = 0; i < headers.size(); ++i) {
        widths[i] = headers[i].size();
        for (const auto& row : rows) {
            widths[i] = std::max(widths[i], row[i].size());
        }
    }

    auto print_row = [&](const std::vector<std::string>& row) {
        for (std::size_t i = 0; i < row.size(); ++i) {
            std::cout << std::left << std::setw(static_cast<int>(widths[i] + 2)) << row[i];
        }
        std::cout << "\n";
    };

    print_row(headers);
    std::vector<std::string> divider;
    for (std::size_t width : widths) {
        divider.push_back(std::string(width, '-'));
    }
    print_row(divider);
    for (const auto& row : rows) {
        print_row(row);
    }
}

void print_topology_table(const std::vector<TopologySummary>& summaries) {
    const std::vector<std::string> headers = {
        "mesh", "V", "F", "E", "boundary", "nonmanifold", "euler"
    };
    std::vector<std::vector<std::string>> rows;
    for (const TopologySummary& s : summaries) {
        rows.push_back({
            s.name,
            std::to_string(s.vertex_count),
            std::to_string(s.face_count),
            std::to_string(s.edge_count),
            std::to_string(s.boundary_edge_count),
            std::to_string(s.nonmanifold_edge_count),
            std::to_string(s.euler_characteristic),
        });
    }

    std::vector<std::size_t> widths(headers.size(), 0);
    for (std::size_t i = 0; i < headers.size(); ++i) {
        widths[i] = headers[i].size();
        for (const auto& row : rows) {
            widths[i] = std::max(widths[i], row[i].size());
        }
    }

    auto print_row = [&](const std::vector<std::string>& row) {
        for (std::size_t i = 0; i < row.size(); ++i) {
            std::cout << std::left << std::setw(static_cast<int>(widths[i] + 2)) << row[i];
        }
        std::cout << "\n";
    };

    print_row(headers);
    std::vector<std::string> divider;
    for (std::size_t width : widths) {
        divider.push_back(std::string(width, '-'));
    }
    print_row(divider);
    for (const auto& row : rows) {
        print_row(row);
    }
}

void print_cleanup_stats(const std::vector<CleanupIterationStats>& stats) {
    const std::vector<std::string> headers = {
        "iter", "bad before", "collapse edges", "split edges", "collapses", "splits", "V", "F"
    };
    std::vector<std::vector<std::string>> rows;
    for (const CleanupIterationStats& s : stats) {
        rows.push_back({
            std::to_string(s.iteration),
            std::to_string(s.bad_before),
            std::to_string(s.collapse_edges),
            std::to_string(s.split_edges),
            std::to_string(s.collapses),
            std::to_string(s.splits),
            std::to_string(s.vertices),
            std::to_string(s.faces),
        });
    }

    std::vector<std::size_t> widths(headers.size(), 0);
    for (std::size_t i = 0; i < headers.size(); ++i) {
        widths[i] = headers[i].size();
        for (const auto& row : rows) {
            widths[i] = std::max(widths[i], row[i].size());
        }
    }

    auto print_row = [&](const std::vector<std::string>& row) {
        for (std::size_t i = 0; i < row.size(); ++i) {
            std::cout << std::left << std::setw(static_cast<int>(widths[i] + 2)) << row[i];
        }
        std::cout << "\n";
    };

    print_row(headers);
    std::vector<std::string> divider;
    for (std::size_t width : widths) {
        divider.push_back(std::string(width, '-'));
    }
    print_row(divider);
    for (const auto& row : rows) {
        print_row(row);
    }
}

void write_csv(const fs::path& path, const std::vector<MeshQualitySummary>& summaries) {
    if (path.has_parent_path()) {
        fs::create_directories(path.parent_path());
    }
    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("Cannot write " + path.string());
    }

    output << "name,vertices,faces,min_angle_deg,avg_min_angle_deg,max_angle_deg,"
           << "avg_aspect_ratio,low_aspect_count,needle_like_count,cap_like_count,"
           << "near_zero_area_count,bad_triangle_count\n";
    for (const MeshQualitySummary& summary : summaries) {
        const auto row = csv_row(summary);
        for (std::size_t i = 0; i < row.size(); ++i) {
            if (i != 0) {
                output << ",";
            }
            output << row[i];
        }
        output << "\n";
    }
}

void usage() {
    std::cout
        << "Usage:\n"
        << "  meshfix_cpp analyze [--csv out.csv] [--needle-angle a] [--cap-angle a] [--aspect-threshold t] mesh.off ...\n"
        << "  meshfix_cpp topology mesh.off ...\n"
        << "  meshfix_cpp cleanup-degenerate mesh.off --out out.off [--iterations n] [--needle-angle a] [--cap-angle a] [--aspect-threshold t]\n";
}

double parse_double(const std::vector<std::string>& args, std::size_t& index) {
    if (index + 1 >= args.size()) {
        throw std::runtime_error("Missing value for " + args[index]);
    }
    return std::stod(args[++index]);
}

int parse_int(const std::vector<std::string>& args, std::size_t& index) {
    if (index + 1 >= args.size()) {
        throw std::runtime_error("Missing value for " + args[index]);
    }
    return std::stoi(args[++index]);
}

int run_analyze(const std::vector<std::string>& args) {
    QualityOptions options;
    fs::path csv_path;
    bool has_csv = false;
    std::vector<std::string> paths;

    for (std::size_t i = 0; i < args.size(); ++i) {
        if (args[i] == "--csv") {
            if (i + 1 >= args.size()) {
                throw std::runtime_error("Missing value for --csv");
            }
            csv_path = args[++i];
            has_csv = true;
        } else if (args[i] == "--needle-angle") {
            options.needle_angle_deg = parse_double(args, i);
        } else if (args[i] == "--cap-angle") {
            options.cap_angle_deg = parse_double(args, i);
        } else if (args[i] == "--aspect-threshold") {
            options.aspect_threshold = parse_double(args, i);
        } else {
            paths.push_back(args[i]);
        }
    }

    if (paths.empty()) {
        throw std::runtime_error("analyze needs at least one OFF file");
    }

    std::vector<MeshQualitySummary> summaries;
    for (const fs::path& path : collect_off_files(paths)) {
        summaries.push_back(analyze_mesh(read_off(path), options));
    }

    print_quality_table(summaries);
    if (has_csv) {
        write_csv(csv_path, summaries);
        std::cout << "\nWrote " << csv_path.string() << "\n";
    }
    return 0;
}

int run_topology(const std::vector<std::string>& args) {
    if (args.empty()) {
        throw std::runtime_error("topology needs at least one OFF file");
    }

    std::vector<TopologySummary> summaries;
    for (const fs::path& path : collect_off_files(args)) {
        summaries.push_back(analyze_topology(read_off(path)));
    }
    print_topology_table(summaries);
    return 0;
}

int run_cleanup(const std::vector<std::string>& args) {
    if (args.empty()) {
        throw std::runtime_error("cleanup-degenerate needs an input OFF file");
    }

    QualityOptions options;
    fs::path input_path;
    fs::path output_path;
    bool has_input = false;
    bool has_output = false;
    int iterations = 3;

    for (std::size_t i = 0; i < args.size(); ++i) {
        if (args[i] == "--out") {
            if (i + 1 >= args.size()) {
                throw std::runtime_error("Missing value for --out");
            }
            output_path = args[++i];
            has_output = true;
        } else if (args[i] == "--iterations") {
            iterations = parse_int(args, i);
        } else if (args[i] == "--needle-angle") {
            options.needle_angle_deg = parse_double(args, i);
        } else if (args[i] == "--cap-angle") {
            options.cap_angle_deg = parse_double(args, i);
        } else if (args[i] == "--aspect-threshold") {
            options.aspect_threshold = parse_double(args, i);
        } else if (!has_input) {
            input_path = args[i];
            has_input = true;
        } else {
            throw std::runtime_error("Unexpected argument: " + args[i]);
        }
    }

    if (!has_input) {
        throw std::runtime_error("cleanup-degenerate needs an input OFF file");
    }
    if (!has_output) {
        throw std::runtime_error("cleanup-degenerate needs --out");
    }
    if (iterations < 1) {
        throw std::runtime_error("--iterations must be positive");
    }

    Mesh mesh = read_off(input_path);
    const MeshQualitySummary before = analyze_mesh(mesh, options);
    CleanupResult result = cleanup_degenerate(mesh, iterations, options);
    write_off(result.mesh, output_path);
    const MeshQualitySummary after = analyze_mesh(result.mesh, options);

    print_cleanup_stats(result.stats);
    std::cout << "\n";
    print_quality_table({before, after});
    std::cout << "\nWrote " << output_path.string() << "\n";
    return 0;
}

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            usage();
            return 2;
        }

        const std::string command = argv[1];
        std::vector<std::string> args;
        for (int i = 2; i < argc; ++i) {
            args.emplace_back(argv[i]);
        }

        if (command == "analyze") {
            return run_analyze(args);
        }
        if (command == "topology") {
            return run_topology(args);
        }
        if (command == "cleanup-degenerate") {
            return run_cleanup(args);
        }

        usage();
        return 2;
    } catch (const std::exception& exc) {
        std::cerr << "error: " << exc.what() << "\n";
        return 1;
    }
}
