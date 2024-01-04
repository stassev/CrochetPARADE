
//Copyright (C) Svetlin Tassev

// This file is part of CrochetPARADE.

// CrochetPARADE is free software: you can redistribute it and/or modify it under 
// the terms of the GNU General Public License as published by the Free Software 
// Foundation, either version 3 of the License, or (at your option) any later version.

// CrochetPARADE is distributed in the hope that it will be useful, but WITHOUT 
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
// FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

// You should have received a copy of the GNU General Public License along 
// with CrochetPARADE. If not, see <https://www.gnu.org/licenses/>.
#include <iostream>
#include <regex>
#include <unordered_map>
#include <queue>
//#include </usr/include/omp.h>
#include <cmath>
#include <string>
#include <sstream>
#include <limits>
const double INF = std::numeric_limits<double>::infinity();

struct Edge {
    int source, destination;
    double weight;
};

struct Graph {
    int num_nodes;
    std::vector<double> flat_distance_matrix;
    std::vector<bool> flat_immediate_neighbor;
    std::vector<std::string> nodes;
    std::vector<std::vector<int>> neighbors;
    std::vector<int> N_neighbors;
    std::vector<std::vector<double>> dist_to_neighbor; 

    Graph(int n) : num_nodes(n), nodes(n, ""), N_neighbors(n, 0),dist_to_neighbor(n,std::vector<double>()) {
        flat_distance_matrix.resize(n * n, INF);
        flat_immediate_neighbor.resize(n * n, false);
        neighbors.resize(n);

        for (int i = 0; i < n; ++i) {
            flat_distance_matrix[i * n + i] = 0.0;
            flat_immediate_neighbor[i * n + i] = true;
        }
    }

    void addEdge(int source, int destination, double weight) {
        flat_distance_matrix[source * num_nodes + destination] = weight;
        flat_distance_matrix[destination * num_nodes + source] = weight;
        flat_immediate_neighbor[source * num_nodes + destination] = true;
        flat_immediate_neighbor[destination * num_nodes + source] = true;
        neighbors[source].push_back(destination);
        neighbors[destination].push_back(source);
        dist_to_neighbor[source].push_back(weight);
        dist_to_neighbor[destination].push_back(weight);
        N_neighbors[source]++;
        N_neighbors[destination]++;
    }

    void addNode(int n, std::string str) {
        nodes[n] = str;
    }


};


struct EdgeInfo {
    std::string source;
    std::string target;
    double len;
};


Graph readDotFile(const std::string& dotContent, int* Ndim, int* seed, int* iterations,double* deflate,int* embedding_dimensions,double* learningRate,bool*deflateQ) {
    std::unordered_map<std::string, int> nodeIndexMap;
    std::vector<EdgeInfo> edges;

    std::string line;
    bool isNodeDefinition = false;
    bool isEdgeDefinition = false;
    size_t i_nodes = 0;

    size_t pos = dotContent.find('\n');
    std::string firstLine = dotContent.substr(0, pos);
    *Ndim = std::stoi(firstLine);  // Convert the first line to an integer and assign it to Ndim

    // Update the position to start reading from the next line
    size_t prevPos = pos + 1;

    //size_t pos = 0;
    //size_t prevPos = 0;
    while (pos != std::string::npos) {
        pos = dotContent.find('\n', prevPos);
        line = dotContent.substr(prevPos, pos - prevPos);

        // Strip leading white spaces
        line.erase(line.begin(), std::find_if(line.begin(), line.end(), [](unsigned char ch) {
            return !std::isspace(ch);
        }));

        if (line.find("\" -- \"") != std::string::npos && line[0] == '"') {
            isEdgeDefinition = true;
            isNodeDefinition = false;
        } else if (!line.empty() && line[0] == '"') {
            isNodeDefinition = true;
            isEdgeDefinition = false;
        } else {
            isNodeDefinition = false;
            isEdgeDefinition = false;
            {
                size_t found = line.find("start");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789", found);
                    size_t end = line.find_first_not_of("0123456789", found);
                    *seed = std::stoi(line.substr(found, end - found));
                }
            }
            {
                size_t found = line.find("iterations");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789", found);
                    size_t end = line.find_first_not_of("0123456789", found);
                    *iterations = std::stoi(line.substr(found, end - found));
                }
            }
            {
                size_t found = line.find("deflate");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789.", found);
                    size_t end = line.find_first_not_of("0123456789.", found);
                    *deflate = std::stod(line.substr(found, end - found));
                    *deflateQ=true;
                }
            }
            {
                size_t found = line.find("embedding_dimensions");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789", found);
                    size_t end = line.find_first_not_of("0123456789", found);
                    *embedding_dimensions = std::stoi(line.substr(found, end - found));
                }else{*embedding_dimensions = *Ndim;}
            }
            {
                size_t found = line.find("learning_rate");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789.", found);
                    size_t end = line.find_first_not_of("0123456789.", found);
                    *learningRate = std::stod(line.substr(found, end - found));
                }
            }
        }

        if (isNodeDefinition) {
            std::smatch matchResult;
            if (std::regex_search(line, matchResult, std::regex("\"([^\"]+)\"\\s*"))) {
                std::string nodeName = matchResult[1];
                nodeIndexMap[nodeName] = static_cast<int>(i_nodes++);
            }
        }

        if (isEdgeDefinition) {
            std::smatch matchResult;
            if (std::regex_search(line, matchResult, std::regex("\"([^\"]+)\"\\s*--\\s*\"([^\"]+)\"\\s*([^\\s]+)"))) {
                EdgeInfo edgeInfo;
                edgeInfo.source = matchResult[1];
                edgeInfo.target = matchResult[2];
                edgeInfo.len = std::stod(matchResult[3]);
                edges.push_back(edgeInfo);
            }
        }

        prevPos = pos + 1;
    }

    Graph graph(i_nodes);

    for (auto it = nodeIndexMap.begin(); it != nodeIndexMap.end(); ++it) {
        graph.addNode(it->second, it->first);
    }

    for (const auto& edge : edges) {
        auto sourceIt = nodeIndexMap.find(edge.source);
        auto targetIt = nodeIndexMap.find(edge.target);

        if (sourceIt != nodeIndexMap.end() && targetIt != nodeIndexMap.end()) {
            int sourceIndex = sourceIt->second;
            int targetIndex = targetIt->second;
            graph.addEdge(sourceIndex, targetIndex, edge.len);
        } else {
            // Handle error: node not found
            std::cerr << "Error: Node not found for edge: " << edge.source << " -- " << edge.target << std::endl;
        }
    }

    return graph;
}


void dijkstra(Graph& graph, int start_node) {
    std::vector<double> distances(graph.num_nodes, INF);
    std::vector<bool> processed(graph.num_nodes, false);
    std::priority_queue<std::pair<double, int>, std::vector<std::pair<double, int>>, std::greater<std::pair<double, int>>> pq;

    pq.push({0, start_node});
    distances[start_node] = 0;

    while (!pq.empty()) {
        int u = pq.top().second;
        pq.pop();

        if (processed[u]) continue;
        processed[u] = true;

        double weight = distances[u];
        if (weight == INF) break;

        for (int k = 0; k < graph.N_neighbors[u]; ++k) {
            int v = graph.neighbors[u][k];
            double weight1 = graph.dist_to_neighbor[u][k];
            if ((weight1 + weight < distances[v])) {
                distances[v] = weight1 + weight;
                pq.push({distances[v], v});
                processed[v] = false; // is this really needed?
            }
        }
    }

    // Copy the computed distances back to the graph's distance matrix
    for (int i = 0; i < graph.num_nodes; ++i) {
        if (!graph.flat_immediate_neighbor[start_node * graph.num_nodes + i]) {
            graph.flat_distance_matrix[start_node * graph.num_nodes + i] = distances[i];
        }
    }
}

extern "C" const char* performLayout(const char* jsInput) {

   // Read dotContent from the standard input
//    std::string jsInput;
    //std::getline(std::cin, dotContent);
    std::string dotContent(jsInput);
    int Ndim;
    int seed=rand();
    int iterations = 500;
    double deflate=1.0;
    int embedding_dimensions;
    double learningRate = 0.1;
    bool deflateQ=false;
    Graph graph= readDotFile(dotContent,&Ndim,&seed,&iterations,&deflate,&embedding_dimensions,&learningRate,&deflateQ);
    const int numDimensions =embedding_dimensions;
    //const int num_threads = 1; // Set the desired number of threads
    //omp_set_num_threads(num_threads);
    //#pragma omp parallel
    {
        //#pragma omp for nowait
        for (int i = 0; i < graph.num_nodes; ++i) {
            dijkstra(graph, i);
        }
    }

// Print the distance matrix
//for (int i = 0; i < graph.num_nodes; ++i) {
//    for (int j = 0; j < graph.num_nodes; ++j) {
//        double distance = graph.flat_distance_matrix[i * graph.num_nodes + j];
//        if (distance == INF) {
//            std::cout << "INF ";
//        } else {
//            std::cout << distance << " ";
//        }
//    }
//    std::cout << std::endl;
//}

    //const int Ndim = 2;
    
    std::vector<double> flat_positions(graph.num_nodes * numDimensions, 0.0);
    std::vector<double> flat_forces(graph.num_nodes * numDimensions, 0.0);

    // Initialize positions
    //int seed = 42; // Starting seed
    srand(seed);   // Seed the random number generator
    for (int i = 0; i < graph.num_nodes*numDimensions; ++i) {
            flat_positions[i] = (static_cast<double>(rand()) / static_cast<double>(RAND_MAX) - 0.5) *10.;
    }

    //int n_edges=0;
    ////#pragma omp parallel for// reduction(+:n_edges)
    //for (int i = 0; i < graph.num_nodes-1; ++i) {
    //    for (int j = i+1; j < graph.num_nodes; ++j) {
    //        if (graph.flat_immediate_neighbor[i * graph.num_nodes + j])
    //            n_edges++;
    //    }
    //}



    // forces

    std::ostringstream jsOutput;
    
    
    for (int iter = 0; iter < iterations; iter++) {
        //std::vector<std::vector<double>> private_forces_per_thread(omp_get_max_threads(),
        //                                                  std::vector<double>(graph.num_nodes * numDimensions, 0.0));
        //std::vector<double>error_per_thead(omp_get_max_threads(),0);

        //double projection_factor = (double(iter)) / (0.9*double(iterations));
        double projection_factor = (double(iter)) / (double(iterations));
        double pf = 1.0 - pow(10., -4. * (projection_factor));
        pf = (1 - learningRate * pf);
        double extraF = sqrt(1 - projection_factor) + 1.e-3;
        double F = learningRate;
        double sINF=sqrt(INF)-1;
        //double error=0.0;
        
        //#pragma omp parallel// reduction(+:error)
        {
            //std::vector<double> private_forces(graph.num_nodes * numDimensions, 0.0);
            //std::vector<double>& private_forces = private_forces_per_thread[omp_get_thread_num()];
            //std::fill(private_forces.begin(), private_forces.end(), 0.0);
            //double myerr=0.0;

            std::vector<double> delta(numDimensions, 0.0);
            //#pragma omp for nowait
            for (int i = 0; i < graph.num_nodes-1; ++i) {
                for (int j = i+1; j < graph.num_nodes; ++j) {
                    double len = graph.flat_distance_matrix[i * graph.num_nodes + j];
                    if ((len < sINF) && (len > 0)) {
                        len *= len;//
                        double d2 = 0.0;

                        for (int dim = 0; dim < numDimensions; ++dim) {
                            delta[dim]=flat_positions[i * numDimensions + dim] - flat_positions[j * numDimensions + dim];
                            d2 += pow(delta[dim], 2);
                        }
                        //double d12=sqrt(d2);
                        //double force = (d12 - len) / (d12+0.01);
                        double force = 0.5*(d2 - len) / (d2+0.001);
                        
                        if (!graph.flat_immediate_neighbor[i * graph.num_nodes + j]) {
                            
                            //if ((iter>0.667*iterations))
                            //    force=0.0;
                            //else
                            if (deflateQ)
                                force *= extraF/(pow(len,deflate)+0.001); //(std::max(d2, len));
                            else 
                                force *= extraF/(len+0.001);
                            //force *= extraF/std::max(d2, len*len);
                        }
                        //else
                        //    error+=force*force;
                        for (int dim = 0; dim < numDimensions; ++dim) {
                            double df = force * delta[dim];
                            flat_forces[i * numDimensions + dim] += df;
                            flat_forces[j * numDimensions + dim] -= df;
                        }
                    }
                }
            }

            //#pragma omp critical
            //{
            //    // Accumulate private forces into the shared forces array
            //    for (int i = 0; i < graph.num_nodes * numDimensions; ++i) {
            //        flat_forces[i] += private_forces[i];
            //    }
            //}
            //error_per_thead[omp_get_thread_num()]=myerr;
        }

        //for (const double& myerr : error_per_thead) {
        //    error+=myerr;
        //}

        // Combine per-thread private forces outside the parallel region
        //for (const auto& private_forces : private_forces_per_thread) {
        //    //#pragma omp parallel for
        //    for (int i = 0; i < graph.num_nodes * numDimensions; ++i) {
        //        flat_forces[i] += private_forces[i];
        //    }
        //}

        //jsOutput <<"Iter: "<<iter<<"; Error: "<<sqrt(error/(double(n_edges)))<<"\n";

        //#pragma omp parallel
        { 
        //#pragma omp for nowait
        for (int i = 0; i < graph.num_nodes; ++i) {
            for (int dim = 0; dim < numDimensions; ++dim) {
                if (dim >= Ndim)
                    flat_positions[i * numDimensions + dim] *= pf;
                flat_positions[i * numDimensions + dim] -= F * flat_forces[i * numDimensions + dim];
                //if ((iter>0.9*iterations)&&(dim>=Ndim)){
                //    flat_positions[i * numDimensions + dim]=0;
                //}
                flat_forces[i * numDimensions + dim]=0;
            }
        }
        }
    }

    for (int i = 0; i < graph.num_nodes; ++i) {
        jsOutput << "{\"name\": \""<<graph.nodes[i]<<"\",\"pos\": \"";
        jsOutput << flat_positions[i * numDimensions];
        for (int dim = 1; dim < Ndim; ++dim) {
            jsOutput << "," << flat_positions[i * numDimensions + dim];
        }
        jsOutput << "\"},";
        jsOutput << '\n';
    }
    // std::cout<<jsOutput.str();
    // Return the output as a C-style string
    std::string outputString = jsOutput.str();
    // Duplicate the C-style string to ensure its memory is managed correctly
    return strdup(outputString.c_str());


}

int main(){
    return 0;
}
