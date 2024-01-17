
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

struct Jacobian {
    std::string jac1;
    std::string jac2;
    std::string jac3;
    std::string jac4;
};

struct Graph {
    int num_nodes;
    std::vector<double> flat_distance_matrix;
    std::vector<bool> flat_immediate_neighbor;
    std::vector<std::string> nodes;
    std::vector<std::vector<int>> neighbors;
    std::vector<int> N_neighbors;
    std::vector<std::vector<double>> dist_to_neighbor; 
    std::vector<bool> flat_specified_positions;
    std::vector<std::vector<double>> nodes_pos;  // Added vector for node positions
    std::vector<std::vector<int>> jacobians;  // Add the jacobians array


    Graph(int n) : num_nodes(n), nodes(n, ""), N_neighbors(n, 0),
        dist_to_neighbor(n,std::vector<double>()), flat_specified_positions(n, false) ,nodes_pos(n, std::vector<double>()), jacobians(){
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

    void addNode(int n, std::string str, const std::vector<double>& pos = {}) {
        nodes[n] = str;
        if (!pos.empty()) {
            // If coordinates are specified, update the positions and set specified_positions flag
            nodes_pos[n] = pos;//pos.size() == 2 ? std::vector<double>{pos[0], pos[1], 0.0} : pos;
            flat_specified_positions[n] = true;
        } else {
            flat_specified_positions[n] = false;
        }
    }


};


struct EdgeInfo {
    std::string source;
    std::string target;
    double len;
};


Graph readDotFile(const std::string& dotContent, int* Ndim, int* seed, int* iterations,double* inflate,double* learningRate,bool*inflateQ,double*separate) {
    std::unordered_map<std::string, int> nodeIndexMap;
    std::vector<EdgeInfo> edges;
    bool isJacDef = false;  // Add this variable to track Jac definition
    std::vector<Jacobian> jacs;  // Add a vector to store Jacobians

    std::string line;
    bool isNodeDefinition = false;
    bool isEdgeDefinition = false;
    size_t i_nodes = 0;

    size_t pos = dotContent.find('\n');
    std::string firstLine = dotContent.substr(0, pos);
    *Ndim = std::stoi(firstLine);  // Convert the first line to an integer and assign it to Ndim

    // Update the position to start reading from the next line
    size_t prevPos = pos + 1;
    std::vector<std::pair<std::string, std::vector<double>>> tempNodes;


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
            isJacDef=false;
        } else if (line.find("\"---\"") != std::string::npos) {
            isEdgeDefinition = false;
            isNodeDefinition = false;
            isJacDef = true;  // Set isJacDef to true when the line contains ---
        } else if (!line.empty() && line[0] == '"') {
            isNodeDefinition = true;
            isEdgeDefinition = false;
            isJacDef=false;
        } else {
            isNodeDefinition = false;
            isEdgeDefinition = false;
            isJacDef=false;
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
                size_t found = line.find("inflate");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789.", found);
                    size_t end = line.find_first_not_of("0123456789.", found);
                    *inflate = std::stod(line.substr(found, end - found));
                    *inflateQ=true;
                }
            }
            {
                size_t found = line.find("learning_rate");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789.", found);
                    size_t end = line.find_first_not_of("0123456789.", found);
                    *learningRate = std::stod(line.substr(found, end - found));
                }
            }
            {
                size_t found = line.find("separate");
                if (found != std::string::npos) {
                    found = line.find_first_of("0123456789.", found);
                    size_t end = line.find_first_not_of("0123456789.", found);
                    *separate = std::stod(line.substr(found, end - found));
                }
            }
        }

        if (isNodeDefinition) {
            std::smatch matchResult;
            if (std::regex_search(line, matchResult, std::regex("\"([^\"]+)\"\\s*\\{([^}]+)\\}\\s*"))) {
                std::string nodeName = matchResult[1];
                nodeIndexMap[nodeName] = static_cast<int>(i_nodes++);

                std::string posStr = matchResult[2];
                std::vector<double> pos;
                std::istringstream posStream(posStr);
                std::string token;
                while (std::getline(posStream, token, ',')) {
                    pos.push_back(std::stod(token));
                }

                tempNodes.emplace_back(nodeName, pos);
            } else if (std::regex_search(line, matchResult, std::regex("\"([^\"]+)\"\\s*"))) {
                // If only the node name is specified, add the node without positions
                std::string nodeName = matchResult[1];
                nodeIndexMap[nodeName] = static_cast<int>(i_nodes++);
                tempNodes.emplace_back(nodeName, std::vector<double>());
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

        if (isJacDef) {
            std::smatch matchResult;
            if (std::regex_search(line, matchResult, std::regex("\"([^\"]+)\"\\s*---\\s*\"([^\"]+)\"\\s*---\\s*\"([^\"]+)\"\\s*---\\s*\"([^\"]+)\""))) {
                Jacobian jac;
                jac.jac1 = matchResult[1];
                jac.jac2 = matchResult[2];
                jac.jac3 = matchResult[3];
                jac.jac4 = matchResult[4];
                jacs.push_back(jac);  // Push the extracted nodes into the jacs vector
            }
        }

        prevPos = pos + 1;
    }

    Graph graph(i_nodes);

    for (const auto& tempNode : tempNodes) {
        graph.addNode(nodeIndexMap[tempNode.first], tempNode.first, tempNode.second);
    }

    //for (auto it = nodeIndexMap.begin(); it != nodeIndexMap.end(); ++it) {
    //    graph.addNode(it->second, it->first);
    //}

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

    // Loop over jacs and find the indices of the nodes
    for (const auto& jac : jacs) {
        std::vector<int> indices =  {
            nodeIndexMap[jac.jac1],
            nodeIndexMap[jac.jac2],
            nodeIndexMap[jac.jac3],
            nodeIndexMap[jac.jac4]
        };
        graph.jacobians.push_back(indices);  // Copy the indices into the graph.jacobians array
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
    double inflate=2.0;
    double learningRate = 0.1;
    bool inflateQ=false;
    double separate=1.5;
    Graph graph= readDotFile(dotContent,&Ndim,&seed,&iterations,&inflate,&learningRate,&inflateQ,&separate);
    const int numDimensions =Ndim;
    {
        //#pragma omp for nowait
        for (int i = 0; i < graph.num_nodes; ++i) {
            dijkstra(graph, i);
        }
    }
    double sINF=sqrt(INF)-1;
    if (separate>0.01){
        double maxD=-1.;//find max_distance
        for (int i = 0; i < graph.num_nodes-1; ++i) {
            for (int j = i+1; j < graph.num_nodes; ++j) {
                double len = graph.flat_distance_matrix[i * graph.num_nodes + j];
                if ((len < sINF) && (len >= 0)&& (maxD<len)) {
                        maxD=len;
                }
            }
        }
        for (int i = 0; i < graph.num_nodes-1; ++i) {
            for (int j = i+1; j < graph.num_nodes; ++j) {
                if (graph.flat_distance_matrix[i * graph.num_nodes + j]>maxD)
                    graph.flat_distance_matrix[i * graph.num_nodes + j]=maxD*separate; // separate disjoint crochet elements.
            }
        }
    }
    
    std::vector<int> ave_forces(3,0.0);
    double n_ave_F=0.0;
    double n_edges=0.0;

    for (int i = 0; i < graph.num_nodes-1; ++i) {
        for (int j = i+1; j < graph.num_nodes; ++j) {
            if (graph.flat_immediate_neighbor[i * graph.num_nodes + j]) 
                n_edges++;
        }
    }

    if (((Ndim==2)&&(numDimensions==2))){
        std::vector<double> flat_positions(graph.num_nodes * numDimensions, 0.0);
        std::vector<double> flat_forces(graph.num_nodes * numDimensions, 0.0);

        int check_convergence=0;
        bool not_converged=true;
        std::ostringstream jsOutput;
        while (not_converged&&(check_convergence<11)){
            not_converged=false;
            check_convergence++;
            // Initialize positions
            srand(seed);   // Seed the random number generator
            for (int i = 0; i < graph.num_nodes*numDimensions; ++i) {
                if (graph.flat_specified_positions[i / numDimensions]) {
                    flat_positions[i] = graph.nodes_pos[i / numDimensions][i % numDimensions];
                } else {
                    flat_positions[i] = (static_cast<double>(rand()) / static_cast<double>(RAND_MAX) - 0.5) * 10.0;
                }
            }

            // forces

            


            for (int iter = 0; iter < iterations; iter++) {
                double projection_factor = (double(iter)) / (double(iterations));
                double pf = 1.0 - pow(10., -4. * (projection_factor));
                pf = (1 - learningRate * pf);
                double extraF = sqrt(1 - projection_factor) + 1.e-3;
                double F = learningRate;
                double deflating_exponent=pow(projection_factor,inflate)+1;
                double error=0.0;
                {
                    std::vector<double> delta(numDimensions, 0.0);
                    for (int i = 0; i < graph.num_nodes-1; ++i) {
                        for (int j = i+1; j < graph.num_nodes; ++j) {
                            if ((!graph.flat_specified_positions[i]) || (!graph.flat_specified_positions[j])){
                                double len = graph.flat_distance_matrix[i * graph.num_nodes + j];
                                if ((len < sINF) && (len > 0)) {
                                    len *= len;//
                                    double d2 = 0.0;

                                    for (int dim = 0; dim < numDimensions; ++dim) {
                                        delta[dim]=flat_positions[i * numDimensions + dim] - flat_positions[j * numDimensions + dim];
                                        d2 += pow(delta[dim], 2);
                                    }
                                    double force = 0.5*(d2 - len) / (d2+0.001);

                                    if (!graph.flat_immediate_neighbor[i * graph.num_nodes + j]) {
                                        if (inflateQ)
                                            force *= extraF/(pow(len,deflating_exponent)+0.001); //(std::max(d2, len));
                                        else 
                                            force *= extraF/(len+0.001);
                                    }
                                    else
                                        error+=force*force;
                                    for (int dim = 0; dim < numDimensions; ++dim) {
                                        double df = force * delta[dim];
                                        flat_forces[i * numDimensions + dim] += df;
                                        flat_forces[j * numDimensions + dim] -= df;
                                    }
                                }
                            }
                        }
                    }
                }
                std::cout<<"Iteration = "<<iter<<" Error = "<<sqrt(error/n_edges)<<std::endl;

                n_ave_F=0.0;
                for (int i = 0; i < graph.num_nodes; ++i) {
                    if (graph.flat_specified_positions[i]){
                        for (int dim = 0; dim < numDimensions; ++dim) {
                            ave_forces[dim]+=flat_forces[i * numDimensions + dim];
                        }
                        n_ave_F++;
                    }
                }
                if (n_ave_F>0){
                    for (int dim = 0; dim < numDimensions; ++dim) {
                        ave_forces[dim]/=n_ave_F;
                    }
                }
                for (int i = 0; i < graph.num_nodes; ++i) {
                    if (!graph.flat_specified_positions[i]){
                        for (int dim = 0; dim < numDimensions; ++dim) {
                            flat_positions[i * numDimensions + dim] -= F * flat_forces[i * numDimensions + dim];
                            flat_forces[i * numDimensions + dim]=0;
                            double x=flat_positions[i * numDimensions + dim];
                            if (abs(x)>1.e5 || isnan(x)){
                                not_converged=true;
                            }
                        }
                    } 
                    else {
                        for (int dim = 0; dim < numDimensions; ++dim) {
                            flat_positions[i * numDimensions + dim] -= F * ave_forces[dim];
                            flat_forces[i * numDimensions + dim]=0;
                            double x=flat_positions[i * numDimensions + dim];
                            if (abs(x)>1.e5 || isnan(x)){
                                not_converged=true;
                            }
                        }
                    }
                    
                }
                for (int dim = 0; dim < numDimensions; ++dim) 
                    ave_forces[dim]=0;
                if (not_converged){
                    learningRate/=3.;
                    std::cout<<"Failed to converge. Learning rate reduced to: "<<learningRate<<std::endl;
                    break;
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
        std::string outputString = jsOutput.str();
        //std::cout<<outputString;    
        // Duplicate the C-style string to ensure its memory is managed correctly
        return strdup(outputString.c_str());
    } else if (((Ndim==3)&&(numDimensions==3))){ // code below is duplicate. this helps compiler speed up code by about a factor of 3.
        std::vector<double> flat_positions(graph.num_nodes * numDimensions, 0.0);
        std::vector<double> flat_forces(graph.num_nodes * numDimensions, 0.0);

        int check_convergence=0;
        bool not_converged=true;
        std::ostringstream jsOutput;
        while (not_converged&&(check_convergence<11)){
            not_converged=false;
            check_convergence++;
            // Initialize positions
            srand(seed);   // Seed the random number generator
            for (int i = 0; i < graph.num_nodes*numDimensions; ++i) {
                if (graph.flat_specified_positions[i / numDimensions]) {
                    flat_positions[i] = graph.nodes_pos[i / numDimensions][i % numDimensions];
                } else {
                    flat_positions[i] = (static_cast<double>(rand()) / static_cast<double>(RAND_MAX) - 0.5) * 10.0;
                }
            }

            // forces

            


            for (int iter = 0; iter < iterations; iter++) {
                double projection_factor = (double(iter)) / (double(iterations));
                double pf = 1.0 - pow(10., -4. * (projection_factor));
                pf = (1 - learningRate * pf);
                double extraF = sqrt(1 - projection_factor) + 1.e-3;
                double F = learningRate;
                double deflating_exponent=pow(projection_factor,inflate)+1;
                double error=0.0;
                {
                    std::vector<double> delta(numDimensions, 0.0);
                    for (int i = 0; i < graph.num_nodes-1; ++i) {
                        for (int j = i+1; j < graph.num_nodes; ++j) {
                            if ((!graph.flat_specified_positions[i]) || (!graph.flat_specified_positions[j])){
                                double len = graph.flat_distance_matrix[i * graph.num_nodes + j];
                                if ((len < sINF) && (len > 0)) {
                                    len *= len;//
                                    double d2 = 0.0;

                                    for (int dim = 0; dim < numDimensions; ++dim) {
                                        delta[dim]=flat_positions[i * numDimensions + dim] - flat_positions[j * numDimensions + dim];
                                        d2 += pow(delta[dim], 2);
                                    }
                                    double force = 0.5*(d2 - len) / (d2+0.001);

                                    if (!graph.flat_immediate_neighbor[i * graph.num_nodes + j]) {
                                        if (inflateQ)
                                            force *= extraF/(pow(len,deflating_exponent)+0.001); //(std::max(d2, len));
                                        else 
                                            force *= extraF/(len+0.001);
                                    }
                                    else
                                        error+=force*force;
                                    for (int dim = 0; dim < numDimensions; ++dim) {
                                        double df = force * delta[dim];
                                        flat_forces[i * numDimensions + dim] += df;
                                        flat_forces[j * numDimensions + dim] -= df;
                                    }
                                }
                            }
                        }
                    }
                }
                std::cout<<"Iteration = "<<iter<<" Error = "<<sqrt(error/n_edges)<<std::endl;





                n_ave_F=0.0;
                for (int i = 0; i < graph.num_nodes; ++i) {
                    if (graph.flat_specified_positions[i]){
                        for (int dim = 0; dim < numDimensions; ++dim) {
                            ave_forces[dim]+=flat_forces[i * numDimensions + dim];
                        }
                        n_ave_F++;
                    }
                }
                if (n_ave_F>0){
                    for (int dim = 0; dim < numDimensions; ++dim) {
                        ave_forces[dim]/=n_ave_F;
                    }
                }
                for (int i = 0; i < graph.num_nodes; ++i) {
                    if (!graph.flat_specified_positions[i]){
                        for (int dim = 0; dim < numDimensions; ++dim) {
                            flat_positions[i * numDimensions + dim] -= F * flat_forces[i * numDimensions + dim];
                            flat_forces[i * numDimensions + dim]=0;
                            double x=flat_positions[i * numDimensions + dim];
                            if (abs(x)>1.e5 || isnan(x)){
                                not_converged=true;
                            }
                        }
                    } 
                    else {
                        for (int dim = 0; dim < numDimensions; ++dim) {
                            flat_positions[i * numDimensions + dim] -= F * ave_forces[dim];
                            flat_forces[i * numDimensions + dim]=0;
                            double x=flat_positions[i * numDimensions + dim];
                            if (abs(x)>1.e5 || isnan(x)){
                                not_converged=true;
                            }
                        }
                    }
                    
                }
                for (int dim = 0; dim < numDimensions; ++dim) 
                    ave_forces[dim]=0;
                if (not_converged){
                    learningRate/=3.;
                    std::cout<<"Failed to converge. Learning rate reduced to: "<<learningRate<<std::endl;
                    break;
                }



                std::array<double, 3> vx, vy,  vn;  // Arrays to store the vectors
                double norm;  
                for (const auto& item : graph.jacobians) {
                    // Extract the coordinates of the 4 points using the node indices
                    int i1 = item[0];
                    int i2 = item[1];
                    int i3 = item[2];
                    int i4 = item[3];
                    for (int dim = 0; dim < numDimensions; ++dim) {
                        vx[dim]=flat_positions[i3*numDimensions+dim]-flat_positions[i1*numDimensions+dim];
                        vy[dim]=-flat_positions[i3*numDimensions+dim]+flat_positions[i2*numDimensions+dim];
                        //vz[dim]=flat_positions[i4*numDimensions+dim]-flat_positions[i3*numDimensions+dim];
                    }
                    vn[0]=vx[1]*vy[2]-vx[2]*vy[1];
                    vn[1]=-vx[0]*vy[2]+vx[2]*vy[0];
                    vn[2]=vx[0]*vy[1]-vx[1]*vy[0];
                    norm=sqrt(vn[0]*vn[0]+vn[1]*vn[1]+vn[2]*vn[2])+1.e-7;
                    vn[0]/=norm;
                    vn[1]/=norm;
                    vn[2]/=norm;
                    //dot=vz[0]*vn[0]+vz[1]*vn[1]+vz[2]*vn[2];
                    //if (dot<=0){
                        for (int dim = 0; dim < numDimensions; ++dim){
                            flat_positions[i4*numDimensions+dim]=(flat_positions[i3*numDimensions+dim]+flat_positions[i4*numDimensions+dim])/2.+0.2*vn[dim]/2.;
                            //flat_positions[i1*numDimensions+dim]-=0.2*vn[dim]/3.;
                            //flat_positions[i2*numDimensions+dim]-=0.2*vn[dim]/3.;
                            flat_positions[i3*numDimensions+dim]=flat_positions[i4*numDimensions+dim]-0.2*vn[dim];
                            //flat_forces[i4*numDimensions+dim]+=(dot-0.2)/(abs(dot)+1.e-2)*vn[dim];
                            //flat_forces[i1*numDimensions+dim]-=(dot-0.2)/(abs(dot)+1.e-2)*vn[dim]/3.;
                            //flat_forces[i2*numDimensions+dim]-=(dot-0.2)/(abs(dot)+1.e-2)*vn[dim]/3.;
                            //flat_forces[i3*numDimensions+dim]-=(dot-0.2)/(abs(dot)+1.e-2)*vn[dim]/3.;
                        }
                    //}
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
        std::string outputString = jsOutput.str();
        //std::cout<<outputString;    
        // Duplicate the C-style string to ensure its memory is managed correctly
        return strdup(outputString.c_str());
    }
   //return ;
}

int main(){
return 0;}
