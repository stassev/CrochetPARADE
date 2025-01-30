///
///

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
///
import * as THREE from 'three';
import {
    OrbitControls
} from './OrbitControls.js';
import {
    GLTFExporter
} from './GLTFExporter.js';
//import {
//    SVGRenderer
//} from 'three/addons/renderers/SVGRenderer.js'
export default function Generate3DModel(json0, renderer, scene, scene1, backgroundColor) {



    if (renderer != null)
        renderer.dispose();

    if (scene1 != null) {
        while (scene1.children.length > 0) {
            scene1.remove(scene1.children[0]);
        }
    }
    if (scene != null) {
        while (scene.children.length > 0) {
            scene.remove(scene.children[0]);
        }
    }
    if (renderer != null)
        renderer.dispose();


    //    const rendererSVG = new SVGRenderer();
    //    rendererSVG.setSize(window.innerWidth, window.innerHeight);
    //    rendererSVG.setClearColor(0xffffff);
    //    document.body.appendChild(rendererSVG.domElement);
    //    rendererSVG.domElement.setAttribute('xmlns', 'http://www.w3.org/2000/svg');


    var str = JSON.parse(JSON.stringify(json0)); //JSON.parse(json0);
    //console.log(str)
    // Create a scene
    scene = new THREE.Scene();
    scene1 = new THREE.Scene();

    //set background color
    if (backgroundColor === '')
        scene.background = new THREE.Color("rgb(210, 210, 210)");
    else
        scene.background = new THREE.Color(backgroundColor);


    // Create a camera




    // Create a renderer

    const domElement = document.querySelector('canvas');
    if (domElement)
        domElement.parentNode.removeChild(domElement);

    var Dimen = 3;

    const container = document.getElementById('view3d'); // Replace 'yourContainerId' with the actual ID of your predefined HTML element


    renderer = new THREE.WebGLRenderer();

    renderer.setPixelRatio(window.devicePixelRatio);
    // renderer.setSize(window.innerWidth, window.innerHeight);


    // Set the size of the renderer
    var width = container.clientWidth; // Use the client width of the container
    var height = container.clientHeight; // Use the client height of the container

    if (width < 50)
        width = window.innerWidth;
    if (height < 50)
        height = window.innerHeight;

    renderer.setSize(width, height);

    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 100);


    renderer.domElement.setAttribute("id", "3DRender");
    //document.body.appendChild(renderer.domElement);
    container.appendChild(renderer.domElement);

    function on3dViewResize() {
        var width = container.clientWidth;
        var height = container.clientHeight;
        if (width < 50) width = window.innerWidth;
        if (height < 50) height = window.innerHeight;

        renderer.setSize(width, height);
        // Adjust pixel ratio
        //   var pixelRatio = window.devicePixelRatio;
        //var newPixelRatio = pixelRatio * width / height;
        //renderer.setPixelRatio(newPixelRatio);
        // Update the camera aspect ratio
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    }

    // Event listener for the class change in '3dview'
    var view = document.getElementById('view3d');
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.attributeName === "class") {
                on3dViewResize();
            }
        });
    });

    observer.observe(view, {
        attributes: true
    });

    //normalize node positions
    var xm = 0.0,
        ym = 0.0,
        zm = 0.0,
        r2 = 0.0,
        tot = 0.0;
    for (var o of str.objects) {
        //console.log(o.pos)
        var pos = o.pos.split('|')[0].split(',').map(Number);
        if (pos.length == 2)
            pos[2] = 0;
        xm += pos[0];
        ym += pos[1];
        zm += pos[2];
        tot += 1.0;
    }
    //var std = Math.sqrt((xm2 - xm * xm / tot + ym2 - ym * ym / tot + zm2 - zm * zm / tot) / (tot))
    xm = xm / tot;
    ym = ym / tot;
    zm = zm / tot;
    for (let o of str.objects) {
        let pos = o.pos.split('|')[0].split(',').map(Number);
        if (pos.length == 2)
            pos[2] = 0;
        r2 = Math.max(r2, (pos[0] - xm) ** 2 + (pos[1] - ym) ** 2 + (pos[2] - zm) ** 2);
    }
    r2 = Math.sqrt(r2);
    for (let o of str.objects) {
        let pos = o.pos.split('|')[0].split(',').map(Number);
        if (pos.length == 2) {
            pos[2] = 0;
            Dimen = 2;
        }
        o['pos'] = [(pos[0] - xm) / r2, (pos[1] - ym) / r2, (pos[2] - zm) / r2];
    }


    // Create a geometry for the nodes
    const nodeGeometry = new THREE.SphereGeometry(0.006, 8, 4);

    // Create a material for the nodes
    const nodeMaterial = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0.9, 0, 0.9)
    });

    const selectedNodeMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color(0, 0.8, 0)
    });

    var NODES = [];
    var NODEShidden = [];
    var NODES1 = [];
    // Create the nodes
    str.objects.forEach((obj) => {
        if (obj.label.split('|')[0] !== "hidden") {
            const pos = obj.pos; //.split(',').map(Number);
            const node = new THREE.Mesh(nodeGeometry, nodeMaterial);
            node.position.set(pos[0], pos[1], pos[2]);
            node['name_long'] = "<span style='font-size: 16px; font-weight: bold;'>(" + obj.name + ") [" + obj.label.split('|')[0] + "]</span><br><b>C1:</b> &hellip;" + obj.label.split('|')[1] + "&hellip;";
            node['name'] = "<span style='font-size: 16px; font-weight: bold;'>(" + obj.name + ") [" + obj.label.split('|')[0] + "]</span>";
            node['type'] = 0;
            node['id0'] = obj.name.split('|')[0];
            node['row'] = [parseInt(obj.name.split('|')[0].split(',')[0]), parseInt(obj.name.split('|')[0].split(',')[1])];
            node['Color'] = obj.label.split('|')[2];
            scene.add(node);
            NODES.push(node);
        }
    });

    //Find average edge scaling factor
    var lenF = 0.0,
        totLen = 0.0;
    for (let edge of str.edges) {
        edge['Color'] = edge.label;

        const tail = str.objects.find((obj) => obj._gvid === edge.tail);
        const head = str.objects.find((obj) => obj._gvid === edge.head);

        edge['length'] = Math.sqrt((tail.pos[0] - head.pos[0]) ** 2 + (tail.pos[1] - head.pos[1]) ** 2 + (tail.pos[2] - head.pos[2]) ** 2);
        if (['red', 'blue'].includes(edge.color)) {
            lenF += edge.length;
            totLen += parseFloat(edge.len);
        }
    }
    lenF = (lenF / totLen);
    var STATS = '';
    STATS += '\n';
    STATS += ("Radius of the sphere bounding the project is " + String(Math.round(10 / lenF) / 10) + " chain stitches.\nThe sphere is centered at center of the 3D view,\ncoinciding with the center of mass of the stitches.\n");
    //console.log(lenF)
    for (let edge of str.edges) {
        edge['stretch'] = (edge.length / lenF) / parseFloat(edge.len);
        //console.log(edge.stretch)
    }



    // 1. Add a directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 3);
    directionalLight.position.set(0, 0, 3);
    scene.add(directionalLight);

    const directionalLight1 = new THREE.DirectionalLight(0xffffff, 3);
    directionalLight1.position.set(0, 0, -3);
    scene.add(directionalLight1);

    // 2. Add an ambient light
    const ambientLight = new THREE.AmbientLight(0x404040, 3);
    scene.add(ambientLight);

    // Create a material for the edges
    const edgeMaterialBlue = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0, 0, 0.9)
    });

    const edgeMaterialRed = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0.9, 0, 0)
    });

    const edgeMaterialGray = new THREE.MeshLambertMaterial({
        color: new THREE.Color(0.7, 0.7, 0.7)
    });

    const selectedEdgeMaterial = new THREE.LineBasicMaterial({
        color: new THREE.Color(0., 0.8, 0),
        linewidth: 2
    });

    const selectedRowMaterial = new THREE.MeshBasicMaterial({
        color: 0xffff65
    });

    var stLen = {};
    var stTot = {};



    /////////////////////

    //var colorscale = {
    //    0: [165, 0, 38],
    //    1: [215, 48, 39],
    //    2: [244, 109, 67],
    //    3: [253, 174, 97],
    //    4: [254, 224, 144],
    //    5: [224, 243, 248],
    //    6: [171, 217, 233],
    //    7: [116, 173, 209],
    //    8: [69, 117, 180],
    //    9: [49, 54, 149]
    //}

    var colorscale = {
        0: [0., 0, 0.9],
        1: [0., 0, 0.9],
        2: [0.6, 0.6, 0.6],
        3: [0.6, 0.6, 0.6],
        4: [0.6, 0.6, 0.6],
        5: [0.9, 0, 0],
        6: [0.9, 0, 0]
    };

    function color(key) {
        if (key >= 6)
            return colorscale[6].map(function(channel) {
                return channel;
            });
        else if (key <= 0)
            return colorscale[0].map(function(channel) {
                return channel;
            });
        var keys = Object.keys(colorscale).map(Number);
        var lowerKey = Math.max.apply(null, keys.filter(function(k) {
            return k <= key;
        }));
        var upperKey = Math.min.apply(null, keys.filter(function(k) {
            return k > key;
        }));
        var lowerColor = colorscale[lowerKey];
        var upperColor = colorscale[upperKey];
        var t = (key - lowerKey) / (upperKey - lowerKey);
        var interpolatedColor = lowerColor.map(function(channel, i) {
            return channel + t * (upperColor[i] - channel);
        });
        return interpolatedColor.map(function(channel) {
            return channel;
        });
    }


    /////////////////////

    //// Create the edges
    str.edges.forEach((edge) => {

        const tail = str.objects.find((obj) => obj._gvid === edge.tail);
        const head = str.objects.find((obj) => obj._gvid === edge.head);

        edge['start'] = [tail.pos[0], tail.pos[1], tail.pos[2]];
        edge['end'] = [head.pos[0], head.pos[1], head.pos[2]];

        const A = (new THREE.Vector3(tail.pos[0], tail.pos[1], tail.pos[2]));
        const B = (new THREE.Vector3(head.pos[0], head.pos[1], head.pos[2]));

        var row = [parseInt(head.name.split('|')[0].split(',')[0]), parseInt(head.name.split('|')[0].split(',')[1])];
        if ((head.label.split('|')[0] == 'ch')) {
            if (!('ch' in stLen)) {
                stLen['ch'] = 0;
                stTot['ch'] = 0;
            }
            stLen['ch'] += edge.stretch;
            stTot['ch']++;
        } else if ((edge.color == "red")) {
            if (!(head.label.split('|')[0] in stLen)) {
                stLen[head.label.split('|')[0]] = 0;
                stTot[head.label.split('|')[0]] = 0;
            }
            stLen[head.label.split('|')[0]] += edge.stretch;
            stTot[head.label.split('|')[0]]++;
        }


        // const geometry = new THREE.BufferGeometry().setFromPoints(points);
        var material;
        if (edge.color === "red")
            material = edgeMaterialRed;
        else
            material = edgeMaterialBlue;
        //var rgbArray = edge.rgb
        //const color = new THREE.Color(rgbArray[0], rgbArray[1], rgbArray[2]);
        //const material = new THREE.LineBasicMaterial({
        //    color: color,
        //    linewidth: 2
        //});
        //const line = new THREE.Line(geometry, material);



        ///
        const distance = A.distanceTo(B);
        var radius = 0.003;
        var non = false;
        edge['gray'] = 0;
        if (edge.color === 'gray') {
            edge['gray'] = 1;
            radius /= 5.0;
            material = edgeMaterialGray;
            non = true;
        }
        // 2. Create a THREE.CylinderGeometry object
        const geometry = new THREE.CylinderGeometry(radius, radius, distance, 5);

        // 3. Position the cylinder between the two points
        const midpoint = new THREE.Vector3().addVectors(A, B).divideScalar(2);
        const line = new THREE.Mesh(geometry, material);
        line.position.copy(midpoint);

        // 4. Orient the cylinder along the vector formed by the two points
        const direction = new THREE.Vector3().subVectors(B, A).normalize();
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
        line.quaternion.copy(quaternion);

        ///

        line['Color'] = edge.Color;
        line['color'] = edge.color;
        line['type'] = 1;
        //"(" + obj.name + ") [" + obj.label.split('|')[0] + "]<br>" + obj.label.split('|')[1]
        line['name_long'] = "<span style='font-size: 16px; font-weight: bold;'>(" + head.name + ") [" + head.label.split('|')[0] + "]</span><br><b>C1:</b> &hellip;" + head.label.split('|')[1] + "&hellip;<br>" + 'stretched by ' + Math.round(100 * (edge['stretch'] - 1)) + '%';
        line['name'] = "<span style='font-size: 16px; font-weight: bold;'>(" + head.name + ") [" + head.label.split('|')[0] + '] stretched by ' + Math.round(100 * (edge['stretch'] - 1)) + '%</span>';
        line['id0'] = (edge.head).toString() + "-" + (edge.tail).toString();
        line['row'] = row;
        line['stretch'] = edge.stretch;
        scene.add(line);



        var arrowhead;

        // Create a cylinder for the arrowhead; create scene1 objects
        if (!non) {
            const arrowheadGeometry = new THREE.CylinderGeometry(radius, radius * 1.7, distance * 0.2, 10);
            const arrowheadMaterial = new THREE.MeshBasicMaterial({
                color: material.color,
                transparent: true,
                opacity: 0.8
            });
            arrowhead = new THREE.Mesh(arrowheadGeometry, arrowheadMaterial);

            // Position the arrowhead at the midpoint between points A and B
            const arrowheadMidpoint = new THREE.Vector3().addVectors(A, B).divideScalar(2);
            arrowhead.position.copy(arrowheadMidpoint);

            // Orient the arrowhead along the vector formed by the two points
            const arrowheadDirection = new THREE.Vector3().subVectors(B, A).normalize();
            const arrowheadQuaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), arrowheadDirection);
            arrowhead.setRotationFromQuaternion(arrowheadQuaternion);
            arrowhead['row'] = row;
            arrowhead['stretch'] = edge.stretch;
            arrowhead['is_arrow'] = true;
            arrowhead['Color'] = edge.Color;
            arrowhead['type'] = 2;
            // Add the arrowhead to the scene
            scene.add(arrowhead);



            // Create a buffer geometry



            // 3. Position the cylinder between the two points

            const line1 = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
                color: edge.Color
            }));

            line1.position.copy(midpoint);

            // 4. Orient the cylinder along the vector formed by the two points
            line1.quaternion.copy(quaternion);

            // Add the line to the scene
            scene1.add(line1);
            NODES1.push(line1);
        }
        ///



        if (!(non)) {
            NODES.push(line);
            NODES.push(arrowhead);
        } else
            NODEShidden.push(line);

    });
    //console.log(NODES)

    STATS += '\n';
    STATS += 'Average vertical (horizontal for chains) stretching of stitches:\n';
    //console.log(stLen)
    for (let g of Object.keys(stLen))
        if (g !== 'hidden')
            STATS += g + '=' + String(Math.round((stLen[g] / stTot[g] - 1) * 100)) + '%\n';

    STATS += '\n';
    var originalMaterials = [];
    for (var i = 0; i < NODES.length; i++)
        originalMaterials.push(NODES[i].material);

    //scene.fog = new THREE.Fog(0xcccccc, 0.1, 10);
    //scene.fog1 = new THREE.FogExp2(0xcccccc, 0.1);

    //controls
    const controls = new OrbitControls(camera, renderer.domElement);

    controls.enableZoom = true; // Enable zooming
    controls.enablePan = true; // Enable panning
    controls.enableRotate = true; // Enable rotation
    controls.minDistance = 0.01; // Minimum zoom distance
    controls.maxDistance = 20; // Maximum zoom distance
    controls.enableDamping = false; // Enable smooth camera movements

    //controls.update() must be called after any manual changes to the camera's transform
    camera.position.set(0, 0, 2);
    controls.update();

    camera.lookAt(0, 0, 0);
    var wasMouseDown = true;
    var canvasClicked = false;
    var timeoutQ = true;
    var timeoutID = null;

    function onMouseDown(event) {
        if (event.shiftKey && event.button === 0 && event.target === renderer.domElement)
            timeoutQ = !timeoutQ;
        if (!timeoutQ) {
            if (timeoutID != null)
                clearTimeout(timeoutID);
        } else {
            var myLabel = document.getElementById('myLabel');
            try {
                document.body.removeChild(myLabel);
            } catch (error) {}
        }
        if ((event.button === 0) && (canvasClicked)) { // Left mouse button
            wasMouseDown = true;
        }

    }
    document.addEventListener('mousedown', onMouseDown);

    ///Display name of node:


    // Set up the raycaster and mouse position
    var raycaster = new THREE.Raycaster();
    //raycaster.params.Precision = 0.00001;


    var mouse = new THREE.Vector2();

    var I = null;
    var Iold = null;

    // Handle the click event
    var oldmaterial = null;

    function createLabel() {
        var label = document.createElement('div');
        label.setAttribute('id', 'myLabel');
        label.style.position = 'absolute';
        label.style.textAlign = 'center';
        //const rect = renderer.domElement.offsetLeft();
        label.style.top = renderer.domElement.offsetTop + 'px';
        label.style.left = (renderer.domElement.offsetLeft + renderer.domElement.offsetWidth / 2) + 'px';

        label.style.transform = 'translate(-50%, 0)';
        label.style.backgroundColor = 'white';
        label.style.padding = '5px';
        label.style.fontSize = '14pt';
        label.style.width = renderer.domElement.offsetWidth * 0.9 + 'px';
        label.style.zIndex = '1000';
        return label;
    }
    var requestedInfo = true;

    function onMove(event) {

        if (requestedInfo && timeoutQ) {
            // Calculate the mouse position
            //mouse.x = ((event.clientX) / window.innerWidth) * 2 - 1;
            //mouse.y = -((event.clientY) / window.innerHeight) * 2 + 1;
            const rect = renderer.domElement.getBoundingClientRect();
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
            //console.log(event.clientX, event.clientY)
            // Set the raycaster position
            raycaster.setFromCamera(mouse, camera);

            // Get the intersected objects
            var intersects = raycaster.intersectObjects(NODES, false);
            intersects = intersects.filter((element) => (element.object.visible === true) && (!('is_arrow' in element.object)));


            // If there is an intersected object, display its name
            //console.log(intersects[0])
            //if (intersects.length > 0) {
            var label = false;
            if (intersects.length != 0) {
                label = createLabel();
            }
            if (intersects.length == 0) {
                I = null;
            } else if (intersects.length == 1) {
                I = intersects[0];
                label.innerHTML = "<span style='overflow-wrap: break-word; word-wrap: break-word;'>" + I.object.name_long + "</span>";
            } else {
                I = null;
                for (var i of intersects) {
                    if (i.object.type == 0) {
                        //console.log(i)
                        I = i;
                        break;
                    }
                }
                if (I == null)
                    I = intersects[0];

                label.innerHTML = "<span style='overflow-wrap: break-word; word-wrap: break-word;'>" + I.object.name_long + "</span>";
            }

            if ((Iold != null) && ((I == null) || (Iold.object.id0 != I.object.id0)))
                Iold.object.material = oldmaterial;
            //change colors of selected
            if ((I != null) && (Iold == null || (Iold.object.id0 != I.object.id0))) {
                oldmaterial = I.object.material;
                if (I.object.type == 0)
                    I.object.material = selectedNodeMaterial;
                else
                    I.object.material = selectedEdgeMaterial;
            }


            Iold = I;
            //



            var labelOld = document.getElementById('myLabel');
            try {
                if ((I == null) && (labelOld))
                    document.body.removeChild(labelOld);
                if ((!(labelOld)) && (label))
                    document.body.appendChild(label);
                if ((I != null) && (labelOld)) {
                    document.body.removeChild(labelOld);
                    document.body.appendChild(label);
                    //document.body.replaceChild(label, labelOld);
                }
            } catch (error) {}
        }
    }

    //}
    //if ('mousemove' in getEventListeners(document))
    //    for (var a of getEventListeners(document).mousemove)
    //        document.removeEventListener(a.type, a.listener)
    document.addEventListener('mousemove', onMove);
    // Add the click event listener

    function onWindowResize() {

        //camera.aspect = window.innerWidth / window.innerHeight;
        //camera.updateProjectionMatrix();

        //renderer.setSize(window.innerWidth, window.innerHeight);

        on3dViewResize();

    }


    window.addEventListener('resize', onWindowResize);
    var showArrows = true;

    var rowNumber = -1000;
    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('keyup', handleKeyUp);

    document.addEventListener('click', function(event) {
        if (event.target !== renderer.domElement) {
            canvasClicked = false;
        } else
            canvasClicked = true;
    });

    function ScaleRadii(f) {
        for (let i of NODES) {
            if (i.type == 1 || i.type == 2) {
                let h = i.geometry.parameters.height;
                let rt = i.geometry.parameters.radiusTop * f;
                let rb = i.geometry.parameters.radiusBottom * f;
                let n = i.geometry.parameters.radialSegments;
                i.geometry.dispose();
                i.geometry = new THREE.CylinderGeometry(rt, rb, h, n);
            } else if (i.type == 0) {
                let r = i.geometry.parameters.radius * f;
                i.geometry.dispose();
                i.geometry = new THREE.SphereGeometry(r, 8, 4);
            }
        }
        for (let i of NODEShidden)
            if (i.type == 1 || i.type == 2) {
                let h = i.geometry.parameters.height;
                let rt = i.geometry.parameters.radiusTop * f;
                let rb = i.geometry.parameters.radiusBottom * f;
                let n = i.geometry.parameters.radialSegments;
                i.geometry.dispose();
                i.geometry = new THREE.CylinderGeometry(rt, rb, h, n);
            }
        for (let i of NODES1) {
            let h = i.geometry.parameters.height;
            let rt = i.geometry.parameters.radiusTop * f;
            let rb = i.geometry.parameters.radiusBottom * f;
            let n = i.geometry.parameters.radialSegments;
            i.geometry.dispose();
            i.geometry = new THREE.CylinderGeometry(rt, rb, h, n);
        }
    }

    var c_was_pressed = false;
    var factor_radius = 1.0;

    var RESETCOLORS = true;
    var HIDE = str.objects.length - 1;

    //Search and highlight
    function handleKeyDown(event) {
        if (canvasClicked && (event.key === 'i')) {
            requestedInfo = !requestedInfo;
            if (timeoutID != null)
                clearTimeout(timeoutID);
            let myLabel = document.getElementById('myLabel');
            //myLabel.style.display = 'none';
            try {
                document.body.removeChild(myLabel);
            } catch (error) {}
        }
        if (canvasClicked && (event.key === 'c')) {
            setTimeout(function() {
                c_was_pressed = true;
                showArrows = false;
                for (let i of NODES) {
                    i.material = new THREE.MeshLambertMaterial({
                        color: new THREE.Color(i.Color)
                    });
                    if (('is_arrow' in i) || i.type == 0)
                        i.visible = false;
                }
                for (let i of NODEShidden)
                    i.visible = false;
                ScaleRadii(4 / factor_radius); // show all radii as twice the default;
                factor_radius = 4;
            }, 200);
        }
        if (canvasClicked && ((event.key === '+') || (event.key === '=') || (event.key === '-')) && (event.ctrlKey || event.metaKey)) {
            //console.log(NODES)
            event.preventDefault();
            setTimeout(function() {

                let f = 1.259921;
                if (event.key === '-')
                    f = 1.0 / f;
                factor_radius *= f;
                ScaleRadii(f);
            }, 300);
        }
        if (canvasClicked && (event.key === 'v')) {
            setTimeout(function() {
                event.preventDefault();
                showArrows = !showArrows;
                if (showArrows) {
                    var [x, y] = str.objects[HIDE].name.split('|')[0].split(',');

                    for (var i = 0; i < NODES.length; i++) {
                        if (((NODES[i].row[0] == parseInt(x)) && (NODES[i].row[1] <= parseInt(y))) ||
                            ((NODES[i].row[0] < parseInt(x)))) {
                            if ('is_arrow' in NODES[i])
                                NODES[i].visible = true;
                        }
                    }

                } else {
                    for (let i of NODES)
                        if ('is_arrow' in i)
                            i.visible = false;
                }
            }, 300);
        }
        if (canvasClicked && (event.key === 's')) {
            event.preventDefault();
            setTimeout(function() {

                for (var i = 0; i < NODES.length; i++) {
                    if ('stretch' in NODES[i])
                        NODES[i].material = new THREE.MeshLambertMaterial({
                            color: new THREE.Color(...color(7 * (NODES[i].stretch - 1.0) + 3))
                        });
                    else
                        NODES[i].material = edgeMaterialGray;
                }
            }, 200);
        }
        if (canvasClicked && (event.key === 'f' && (event.ctrlKey || event.metaKey))) {
            event.preventDefault();
            setTimeout(function() {

                if (rowNumber != -1000) {
                    for (let i = 0; i < NODES.length; i++) {
                        NODES[i].material = originalMaterials[i];
                    }
                }
                var rn = null;
                rn = (prompt('Enter a row number or stitch coordinate (row,stitch number; e.g. 2,4) to be highlighted'));
                var rr = [];
                if (rn) {
                    for (var r of rn.split(new RegExp('[^0-9]+')))
                        if (r !== '')
                            rr.push(parseInt(r));
                    if (rr.length == 1) {
                        rowNumber = rr[0];
                        //console.log(NODES)
                        for (let i = 0; i < NODES.length; i++) {
                            if (NODES[i].row[0] == rowNumber) {
                                NODES[i].material = selectedRowMaterial;
                            }
                        }
                    } else if (rr.length == 2) {
                        //console.log(NODES)
                        rowNumber = rr[0];
                        for (let i = 0; i < NODES.length; i++) {
                            if ((NODES[i].row[0] == rowNumber) && (NODES[i].row[1] == rr[1])) {
                                NODES[i].material = selectedRowMaterial;
                            }
                        }
                    }
                }
            }, 300);
        }
    }


    function handleKeyUp(event) {
        if (canvasClicked && event.key === 'Escape') {
            event.preventDefault();
            if (!(event.ctrlKey || event.metaKey)) {
                c_was_pressed = false;
                for (let i = 0; i < NODES.length; i++) {
                    NODES[i].material = originalMaterials[i];
                    NODES[i].visible = true;
                }
                for (let i = 0; i < NODEShidden.length; i++) {
                    NODEShidden[i].visible = true;
                }
                RESETCOLORS = true;
                HIDE = str.objects.length - 1;

                ScaleRadii(1 / factor_radius); // show all radii as normal;
                factor_radius = 1;
            } else {
                HIDE = 0;
                RESETCOLORS = false;
                NODES[0].visible = true;
                NODES[0].material = originalMaterials[0];
                for (let i = 1; i < NODES.length; i++) {
                    NODES[i].material = originalMaterials[i];
                    NODES[i].visible = false;
                }
                for (let i = 0; i < NODEShidden.length; i++) {
                    //NODEShidden[i].material = originalMaterials[i];
                    NODEShidden[i].visible = false;
                }
            }
        }
    }
    //Search and hide.

    document.addEventListener('keydown', handleKeyDownHide, true);

    function handleKeyDownHide(event) {
        if ((canvasClicked) && (event.key === 'r')) {
            wasMouseDown = false;
        }
        if (canvasClicked && (event.key === 'p')) {
            setTimeout(function() {
                saveSvg();
            }, 300);
        }
        if (canvasClicked && (event.key === 'h' && (event.ctrlKey || event.metaKey))) {


            event.preventDefault();
            setTimeout(function() {
                if (rowNumber != -1000) {
                    for (let i = 0; i < NODES.length; i++) {
                        NODES[i].material = originalMaterials[i];
                        NODES[i].visible = true;
                    }
                }
                //var rn = null
                //rn = (prompt('Enter a row number or stitch coordinate (row,stitch number; e.g. 2,4). All stitches after that will be hidden'));

                var rn = null;
                rn = (prompt('Enter a row number or stitch coordinate (row,stitch number; e.g. 2,4). All stitches after that will be hidden'));
                var rr = [];
                if (rn) {
                    for (let r of rn.split(new RegExp('[^0-9]+')))
                        if (r !== '')
                            rr.push(parseInt(r));
                    if (rr.length == 1) {
                        rowNumber = rr[0];
                        //console.log(NODES)
                        for (let i = 0; i < NODES.length; i++) {
                            if (NODES[i].row[0] > rowNumber) {
                                NODES[i].visible = false;
                            }
                        }
                        for (let i = 0; i < NODEShidden.length; i++) {
                            if (NODEShidden[i].row[0] > rowNumber) {
                                NODEShidden[i].visible = false;
                            }
                        }

                        RESETCOLORS = false;

                        HIDE = str.objects.findIndex((obj) => obj.name.split('|')[0] === String(rr[0] + 1) + ',' + String(0));
                        HIDE--;
                        if (HIDE == -2) { //searching for last element
                            HIDE = str.objects.length - 1;
                            //while ((str.objects[HIDE].label.split('|')[0] === "hidden") && HIDE >= 0)
                            //    HIDE--
                        }

                        if (HIDE == -1)
                            HIDE = 0;
                    } else if (rr.length == 2) {
                        //console.log(NODES)
                        rowNumber = rr[0];
                        for (var i = 0; i < NODES.length; i++) {
                            if (((NODES[i].row[0] == rowNumber) && (NODES[i].row[1] > rr[1])) || (NODES[i].row[0] > rowNumber)) {
                                NODES[i].visible = false;
                            }
                        }

                        for (let i = 0; i < NODEShidden.length; i++) {
                            if (((NODEShidden[i].row[0] == rowNumber) && (NODEShidden[i].row[1] > rr[1])) || (NODEShidden[i].row[0] > rowNumber)) {
                                NODEShidden[i].visible = false;
                            }
                        }

                        RESETCOLORS = false;

                        HIDE = str.objects.findIndex((obj) => obj.name.split('|')[0] === String(rr[0]) + ',' + String(rr[1]));
                        if (HIDE == -1)
                            HIDE = 0;

                    } {
                        let myLabel = document.getElementById('myLabel');
                        //myLabel.style.display = 'none';
                        try {
                            document.body.removeChild(myLabel);
                        } catch (error) {}
                    }
                    if (requestedInfo) {
                        let label = createLabel();
                        //console.log(str.objects[HIDE].name)
                        label.innerHTML = "<span style='font-size: 16px; font-weight: bold;'>" + str.objects[HIDE].name + '</span>';
                        document.body.appendChild(label);
                        if (timeoutID != null)
                            clearTimeout(timeoutID);
                        if (timeoutQ)
                            timeoutID = setTimeout(() => {
                                var myLabel = document.getElementById('myLabel');
                                //myLabel.style.display = 'none';
                                try {
                                    document.body.removeChild(myLabel);
                                } catch (error) {}
                            }, 10000);
                    }
                }
            }, 300);

        }
    }

    //Search and hide.

    document.addEventListener('keydown', handleKeyDownHideAnim);


    function handleKeyDownHideAnim(event) {

        if (canvasClicked && (event.key === 'a')) {
            event.preventDefault();
            if ((event.ctrlKey || event.metaKey)) {
                if (RESETCOLORS) {
                    RESETCOLORS = false;
                    HIDE = str.objects.length - 1;
                }
                if (HIDE > str.objects.length)
                    HIDE = str.objects.length - 1;
                HIDE--;
                while ((HIDE >= 0) && (str.objects[HIDE].label.split('|')[0] === "hidden"))
                    HIDE--;

                if (HIDE < 0)
                    HIDE = 0;
                let [x, y] = str.objects[HIDE].name.split('|')[0].split(',');

                for (let i = 0; i < NODES.length; i++) {
                    if (((NODES[i].row[0] >= parseInt(x)) && (NODES[i].row[1] > parseInt(y))) ||
                        ((NODES[i].row[0] > parseInt(x)))) {
                        NODES[i].visible = false;
                    }
                }

                for (let i = 0; i < NODEShidden.length; i++) {
                    if (((NODEShidden[i].row[0] >= parseInt(x)) && (NODEShidden[i].row[1] > parseInt(y))) ||
                        ((NODEShidden[i].row[0] > parseInt(x)))) {
                        NODEShidden[i].visible = false;
                    }
                }

            } else {
                HIDE++;
                if (HIDE > str.objects.length - 1)
                    HIDE = str.objects.length - 1;
                //while ((str.objects[HIDE].label.split('|')[0] === "hidden") && HIDE >= 0)
                //    HIDE--

                while ((HIDE < str.objects.length) && (str.objects[HIDE].label.split('|')[0] === "hidden"))
                    HIDE++;


                if (HIDE >= str.objects.length)
                    HIDE = str.objects.length - 1;
                if (HIDE == str.objects.length - 1 && str.objects[HIDE].label.split('|')[0] === "hidden")
                    while ((HIDE >= 0) && (str.objects[HIDE].label.split('|')[0] === "hidden"))
                        HIDE--;
                if ((HIDE < str.objects.length)) {
                    if (str.objects[HIDE].label.split('|')[0] !== "hidden") {
                        let [x, y] = str.objects[HIDE].name.split('|')[0].split(',');

                        for (let i = 0; i < NODES.length; i++) {
                            if ((NODES[i].row[0] <= parseInt(x)) && (NODES[i].row[1] <= parseInt(y))) {
                                if (!((!showArrows) && ('is_arrow' in NODES[i])))
                                    NODES[i].visible = true;
                            }
                        }

                        for (let i = 0; i < NODEShidden.length; i++) {
                            if ((NODEShidden[i].row[0] <= parseInt(x)) && (NODEShidden[i].row[1] <= parseInt(y))) {
                                NODEShidden[i].visible = true;
                            }
                        }
                    }
                }
            }

            if (requestedInfo) {
                {
                    let myLabel = document.getElementById('myLabel');
                    //myLabel.style.display = 'none';
                    try {
                        document.body.removeChild(myLabel);
                    } catch (error) {}
                }
                let label = createLabel();

                //label.innerHTML = "<span style='font-size: 16px; font-weight: bold;'>" + str.objects[HIDE].name + '</span>'
                label.innerHTML = "<span style='overflow-wrap: break-word; word-wrap: break-word;'><span style='font-size: 16px; font-weight: bold;'>(" + str.objects[HIDE].name + ") [" + str.objects[HIDE].label.split('|')[0] + "]</span><br><b>C1:</b> &hellip;" + str.objects[HIDE].label.split('|')[1] + "&hellip;</span>";
                document.body.appendChild(label);
                if (timeoutID != null)
                    clearTimeout(timeoutID);
                if (timeoutQ)
                    timeoutID = setTimeout(() => {
                        var myLabel = document.getElementById('myLabel');
                        try {
                            document.body.removeChild(myLabel);
                        } catch (error) {}
                    }, 10000);
            }

            if (c_was_pressed) {
                for (let i of NODES) {
                    if (('is_arrow' in i) || i.type == 0)
                        i.visible = false;
                }
                for (let i of NODEShidden)
                    i.visible = false;
            }

        }
    }

    function saveSvg() {
        let size;

        function tightenAndCenterBBox(draw, svgPath) {
            //console.log('ok1');
            const tempPath = draw.path(svgPath);
            //console.log('ok2');
            const bbox = tempPath.bbox();
            //console.log('ok3');
            tempPath.remove();
            //console.log('ok4');

            const centerX = bbox.x + bbox.width / 2;
            const centerY = bbox.y + bbox.height / 2;
            //console.log(centerX, centerY);

            const centeredPath = svgPath.replace(/([MLHVCSQTAZ])([^MLHVCSQTAZ]*)/g, (match, cmd, args) => {
                if (cmd === 'Z') return cmd;
                const coords = args.trim().split(/[\s,]+/).map(parseFloat);
                switch (cmd.toUpperCase()) {
                    case 'A':
                        coords[5] -= centerX;
                        coords[6] -= centerY;
                        break;
                    case 'V':
                        coords[0] -= centerY;
                        break;
                    case 'H':
                        coords[0] -= centerX;
                        break;
                    default:
                        for (let i = 0; i < coords.length; i++) {
                            coords[i] -= (i % 2 === 0) ? centerX : centerY;
                        }
                }
                return cmd + coords.join(',');
            });
            //console.log(centeredPath);
            return centeredPath;
        }

        function scalePathData(pathData, scaleX, scaleY) {
            return pathData.replace(/([MLHVCSQTAZ])([^MLHVCSQTAZ]*)/g, (match, cmd, args) => {
                if (cmd === 'Z') return cmd;
                const coords = args.trim().split(/[\s,]+/).map(parseFloat);
                switch (cmd.toUpperCase()) {
                    case 'A':
                        coords[0] *= scaleX;
                        coords[1] *= scaleY;
                        coords[5] *= scaleX;
                        coords[6] *= scaleY;
                        break;
                    case 'V':
                        coords[0] *= scaleY;
                        break;
                    case 'H':
                        coords[0] *= scaleX;
                        break;
                    default:
                        for (let i = 0; i < coords.length; i++) {
                            coords[i] *= (i % 2 === 0) ? scaleX : scaleY;
                        }
                }
                return cmd + coords.join(',');
            });
        }

        function addCrochetSymbolsBetweenNodes(draw, nodes, edges) {
            const symbolMap = {
                'ch': 'M-5,0 A5,10 0 1,1 5,0 A5,10 0 1,1 -5,0',
                'ss': 'M0,5 A5,5 0 1,1 0,-5 A5,5 0 1,1 0,5 Z',
                'sc': 'M171.94102,111.30121 H179.71246 M175.82674,117.09468 V105.50773',
                'hdc': 'M181.17536,80.290159 H190.91306 M186.2474,99.048099 V80.157868',
                'dc': 'M168.02921,73.65257 H177.76691 M172.89806,96.912628 V73.520279 M170.84091,82.837921 L174.95521,85.213321',
                'tr': 'M102.7556,85.196435 L106.8699,87.571832 M99.9439,70.719415 H109.6816 M104.81275,102.98371 V70.587124 M102.7556,82.021436 L106.8699,84.396833',
                'dtr': 'M120.04696,61.90545 H129.78466 M124.91581,102.3795 V61.773159 M122.85866,75.853306 L126.97296,78.228703 M122.85866,78.499138 L126.97296,80.874535 M122.85866,81.14497 L126.97296,83.520367',
                'trtr': 'M138.66122,53.519063 H148.39892 M143.53007,101.48366 V53.386772 M141.47292,70.641918 L145.58722,73.017315 M141.47292,73.28775 L145.58722,75.663147 M141.47292,75.933582 L145.58722,78.308979 M141.47292,78.579417 L145.58722,80.954814',
                'rsc': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.48897,145.41015 C133.19121,144.42701 133.70618,144.28657 134.40842,144.28657 C135.11065,144.28657 136.09379,145.45696 136.93648,145.45696 C137.77917,145.45696 138.57503,144.38019 138.57503,144.38019',
                'scbl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.05252,161.34418 A3.5790462,2.8758667 0 0 1 135.63156,158.46831 A3.5790462,2.8758667 0 0 1 139.21061,161.34418',
                'scfl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.05252,158.33667 A3.5790462,2.8758667 0 0 0 135.63156,161.21254 A3.5790462,2.8758667 0 0 0 139.21061,158.33667',
                'hdcfl': 'M59.828576,81.788267 H69.566276 M64.900616,100.54621 V81.655976 M61.321573,100.71371 A3.5790462,2.8758667 0 0 0 64.90062,103.58957 A3.5790462,2.8758667 0 0 0 68.479666,100.71371',
                'dcfl': 'M77.019122,75.899733 H86.756822 M81.887972,99.159791 V75.767442 M79.830822,85.085084 L83.945122,87.460484 M78.308924,99.327293 A3.5790462,2.8758667 0 0 0 81.88797,102.20316 A3.5790462,2.8758667 0 0 0 85.46701,99.327293',
                'trfl': 'M99.9439,70.719415 H109.6816 M104.81275,102.98371 V70.587124 M102.7556,82.021436 L106.8699,84.396833 M102.7556,85.196435 L106.8699,87.571832 M101.23371,103.15121 A3.5790462,2.8758667 0 0 0 104.81275,106.02707 A3.5790462,2.8758667 0 0 0 108.39179,103.15121',
                'dtrfl': 'M120.04696,61.90545 H129.78466 M124.91581,102.3795 V61.773159 M122.85866,75.853306 L126.97296,78.228703 M122.85866,78.499138 L126.97296,80.874535 M122.85866,81.14497 L126.97296,83.520367 M121.33676,102.547 A3.5790462,2.8758667 0 0 0 124.91581,105.42286 A3.5790462,2.8758667 0 0 0 128.49486,102.547',
                'trtrfl': 'M138.66122,53.519063 H148.39892 M143.53007,101.48366 V53.386772 M141.47292,70.641918 L145.58722,73.017315 M141.47292,73.28775 L145.58722,75.663147 M141.47292,75.933582 L145.58722,78.308979 M141.47292,78.579417 L145.58722,80.954814 M139.95103,101.65115 A3.5790462,2.8758667 0 0 0 143.53008,104.52702 A3.5790462,2.8758667 0 0 0 147.10912,101.65115',
                'hdcbl': 'M59.828576,81.788267 H69.566276 M64.900616,100.54621 V81.655976 M61.321573,104.16475 A3.5790462,2.8758667 0 0 1 64.90062,101.28889 A3.5790462,2.8758667 0 0 1 68.479666,104.16475',
                'dcbl': 'M77.019122,75.899733 H86.756822 M81.887972,99.159791 V75.767442 M79.830822,85.085084 L83.945122,87.460484 M78.308924,102.77833 A3.5790462,2.8758667 0 0 1 81.88797,99.90247 A3.5790462,2.8758667 0 0 1 85.46701,102.77833',
                'trbl': 'M99.9439,70.719415 H109.6816 M104.81275,102.98371 V70.587124 M102.7556,82.021436 L106.8699,84.396833 M102.7556,85.196435 L106.8699,87.571832 M101.23371,106.60225 A3.5790462,2.8758667 0 0 1 104.81275,103.72639 A3.5790462,2.8758667 0 0 1 108.39179,106.60225',
                'dtrbl': 'M120.04696,61.90545 H129.78466 M124.91581,102.3795 V61.773159 M122.85866,75.853306 L126.97296,78.228703 M122.85866,78.499138 L126.97296,80.874535 M122.85866,81.14497 L126.97296,83.520367 M121.33676,105.99804 A3.5790462,2.8758667 0 0 1 124.91581,103.12218 A3.5790462,2.8758667 0 0 1 128.49486,105.99804',
                'trtrbl': 'M138.66122,53.519063 H148.39892 M143.53007,101.48366 V53.386772 M141.47292,70.641918 L145.58722,73.017315 M141.47292,73.28775 L145.58722,75.663147 M141.47292,75.933582 L145.58722,78.308979 M141.47292,78.579417 L145.58722,80.954814 M139.95103,105.10219 A3.5790462,2.8758667 0 0 1 143.53008,102.22633 A3.5790462,2.8758667 0 0 1 147.10912,105.10219',
                'rscfl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.58916,145.41015 C133.2914,144.42701 133.80637,144.28657 134.50861,144.28657 C135.21084,144.28657 136.19398,145.45696 137.03667,145.45696 C137.87936,145.45696 138.67522,144.38019 138.67522,144.38019 M132.05252,158.33667 A3.5790462,2.8758667 0 0 0 135.63156,161.21254 A3.5790462,2.8758667 0 0 0 139.21061,158.33667',
                'rscbl': 'M131.74584,151.77464 H139.51728 M135.63156,157.56811 V145.98116 M132.58916,145.41015 C133.2914,144.42701 133.80637,144.28657 134.50861,144.28657 C135.21084,144.28657 136.19398,145.45696 137.03667,145.45696 C137.87936,145.45696 138.67522,144.38019 138.67522,144.38019 M132.05252,161.34418 A3.5790462,2.8758667 0 0 1 135.63156,158.46831 A3.5790462,2.8758667 0 0 1 139.21061,161.34418',
                'fphdc': 'M33.011523,141.15521 H42.749223 M37.880373,159.91315 V141.02292 M37.880363,159.78142 A4.7955728,4.7955728 0 0 1 42.310895,162.74181 A4.7955728,4.7955728 0 0 1 41.271345,167.96798 A4.7955728,4.7955728 0 0 1 36.045177,169.00753 A4.7955728,4.7955728 0 0 1 33.084791,164.577',
                'fpdc': 'M61.912498,143.00729 H71.650198 M66.781348,166.26735 V142.875 M64.724198,152.19264 L68.838498,154.56804 M66.781342,166.13465 A4.7955728,4.7955728 0 0 1 71.211873,169.09499 A4.7955728,4.7955728 0 0 1 70.172323,174.32116 A4.7955728,4.7955728 0 0 1 64.946155,175.36071 A4.7955728,4.7955728 0 0 1 61.985769,170.93022',
                'fptr': 'M83.918311,134.29161 H93.656011 M88.787161,166.55591 V134.15932 M86.730011,145.59363 L90.844311,147.96903 M86.730011,148.76863 L90.844311,151.14403 M88.787148,166.42292 A4.7955728,4.7955728 0 0 1 93.217679,169.38330 A4.7955728,4.7955728 0 0 1 92.178129,174.60947 A4.7955728,4.7955728 0 0 1 86.951961,175.64902 A4.7955728,4.7955728 0 0 1 83.991575,171.21849',
                'bphdc': 'M33.011523,141.15521 H42.749223 M37.880373,159.91315 V141.02292 M37.880383,159.78142 A4.7955728,4.7955728 0 0 0 33.449851,162.74181 A4.7955728,4.7955728 0 0 0 34.489401,167.96798 A4.7955728,4.7955728 0 0 0 39.715569,169.00753 A4.7955728,4.7955728 0 0 0 42.675955,164.577',
                'bpdc': 'M61.912498,143.00729 H71.650198 M66.781348,166.26735 V142.875 M64.724198,152.19264 L68.838498,154.56804 M66.781364,166.13465 A4.7955728,4.7955728 0 0 0 62.350833,169.09504 A4.7955728,4.7955728 0 0 0 63.390383,174.32120 A4.7955728,4.7955728 0 0 0 68.616551,175.36075 A4.7955728,4.7955728 0 0 0 71.576937,170.93022',
                'bptr': 'M83.918311,134.29161 H93.656011 M88.787161,166.55591 V134.15932 M86.730011,145.59363 L90.844311,147.96903 M86.730011,148.76863 L90.844311,151.14403 M88.78717,166.42292 A4.7955728,4.7955728 0 0 0 84.356639,169.38330 A4.7955728,4.7955728 0 0 0 85.396189,174.60947 A4.7955728,4.7955728 0 0 0 90.622357,175.64902 A4.7955728,4.7955728 0 0 0 93.582743,171.21849',
                'bpsc': 'M29.10417,197.88098 H36.87561 M32.98989,203.67445 V192.0875 M32.989899,203.54151 A4.7955728,4.7955728 0 0 0 28.559367,206.50190 A4.7955728,4.7955728 0 0 0 29.598917,211.72806 A4.7955728,4.7955728 0 0 0 34.825085,212.76761 A4.7955728,4.7955728 0 0 0 37.785471,208.33708',
                'fpsc': 'M29.10417,197.88098 H36.87561 M32.98989,203.67445 V192.0875 M32.98988,203.54151 A4.7955728,4.7955728 0 0 1 37.420411,206.50190 A4.7955728,4.7955728 0 0 1 36.380862,211.72806 A4.7955728,4.7955728 0 0 1 31.154693,212.76761 A4.7955728,4.7955728 0 0 1 28.194307,208.33708',
                'line': 'M0,-5 L0,5',
                'long_sc': 'M86.353122,21.591733 H106.71982 M96.536472,44.851791 V21.459442 M96.536472,42.746442 A13.596,25.696 0 0 1 110.13247,68.442442 A13.596,25.696 0 0 1 96.536472,94.138442',
                'long_dc': 'M0,0 H36.803905 M19.355965,26.333015 L34.907265,35.308015 M22.745129,0 C25.220129,10.605 30.220129,39.235 29.810129,60.815 C29.405129,82.355 26.275129,103.595 23.105129,158.375',
                'long_tr': 'M5,0 H41.803905 M19.355965,26.333015 L34.907265,35.308015 M19.355965,36.899015 L34.907265,45.874015 M22.745129,0 C25.220129,10.605 30.220129,54.095 29.810129,75.675 C29.405129,97.215 26.275129,122.455 23.105129,177.235'
            };


            nodes.forEach(node => {
                let name = node.name.split('|')[0];
                let vis = false;
                for (let j = 0; j < NODES.length; j++) {
                    if (name === NODES[j].id0) {
                        // Match found
                        vis = NODES[j].visible;
                        break;
                    }
                }

                if (vis && (node.label.split('|')[0] !== "hidden")) {
                    const nodeId = node.label.split('|')[0];
                    const edge1 = edges.find(edge => edge.head === node._gvid && edge.color === 'blue');
                    const edge2 = edges.find(edge => edge.tail === node._gvid && edge.color === 'blue');

                    if (edge1 && edge2) {
                        if (nodeId === 'ch') {
                            drawChainBetweenEdges(draw, edge1, edge2, size, symbolMap['ch']);
                        } else {
                            drawLineBetweenEdges(draw, edge1, edge2, size, 'plum', 1);
                        }
                    } else if (edge2) {
                        if (nodeId === 'ch') {
                            drawChainBetweenEdges(draw, null, edge2, size, symbolMap['ch']);
                        }
                    }

                    if (nodeId !== 'ch') {
                        const incomingRedEdges = edges.filter(edge =>
                            edge.head === node._gvid && edge.color === 'red'
                        );
                        incomingRedEdges.forEach(edge => {
                            const symbol = symbolMap[nodeId] || 'M0,-2.5 L0,2.5';
                            drawSymbolAlongEdge(draw, edge, symbol, size, false, nodeId);
                        });
                    }
                }
            });
        }

        function drawChainBetweenEdges(draw, edge1, edge2, size, symbolPath) {
            let x1, y1, x2, y2;

            // Calculate average points
            let avgPoint1, avgPoint2;
            if (edge1 === null) {
                avgPoint1 = edge2.start.map((coord, i) => coord - (edge2.end[i] - edge2.start[i]) / 2);
            } else {
                avgPoint1 = edge1.start.map((coord, i) => (coord + edge1.end[i]) / 2);
            }
            avgPoint2 = edge2.start.map((coord, i) => (coord + edge2.end[i]) / 2);

            if (Dimen == 2) {
                x1 = (avgPoint1[0] + 1) * size / 2.0;
                y1 = (-avgPoint1[1] + 1) * size / 2.0;
                x2 = (avgPoint2[0] + 1) * size / 2.0;
                y2 = (-avgPoint2[1] + 1) * size / 2.0;
            } else {
                x1 = (avgPoint1[0] * xR + avgPoint1[1] * yR + avgPoint1[2] * zR + 1) * size / 2.0;
                y1 = (avgPoint1[0] * xU + avgPoint1[1] * yU + avgPoint1[2] * zU + 1) * size / 2.0;
                x2 = (avgPoint2[0] * xR + avgPoint2[1] * yR + avgPoint2[2] * zR + 1) * size / 2.0;
                y2 = (avgPoint2[0] * xU + avgPoint2[1] * yU + avgPoint2[2] * zU + 1) * size / 2.0;
            }

            const angle = Math.atan2(y2 - y1, x2 - x1);
            const edgeLength = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
            //console.log(symbolPath);

            let centeredPath = tightenAndCenterBBox(draw, symbolPath);
            //console.log(centeredPath);

            const tempPath = draw.path(centeredPath);
            const symbolBBox = tempPath.bbox();
            tempPath.remove();

            let scaleY = edgeLength * 0.95 / symbolBBox.height;
            let scaleX = scaleY / 3;


            const symbol = draw.path(centeredPath)
                .fill('none')
                .stroke({
                    color: 'black',
                    width: 1
                });

            const scaledPath = scalePathData(centeredPath, scaleX, scaleY);
            symbol.plot(scaledPath);

            const centerX = (x1 + x2) / 2;
            const centerY = (y1 + y2) / 2;

            symbol.transform({
                translateX: centerX,
                translateY: centerY,
                rotate: (angle + Math.PI / 2.) * 180 / Math.PI,
                originX: 'center',
                originY: 'center'
            });
        }

        function drawLineBetweenEdges(draw, edge1, edge2, size, lineColor = 'green', lineWidth = 1) {
            let x1, y1, x2, y2;

            // Calculate average points
            const avgPoint1 = edge1.start.map((coord, i) => (coord + edge1.end[i]) / 2);
            const avgPoint2 = edge2.start.map((coord, i) => (coord + edge2.end[i]) / 2);

            if (Dimen == 2) {
                x1 = (avgPoint1[0] + 1) * size / 2.0;
                y1 = (-avgPoint1[1] + 1) * size / 2.0;
                x2 = (avgPoint2[0] + 1) * size / 2.0;
                y2 = (-avgPoint2[1] + 1) * size / 2.0;
            } else {
                x1 = (avgPoint1[0] * xR + avgPoint1[1] * yR + avgPoint1[2] * zR + 1) * size / 2.0;
                y1 = (avgPoint1[0] * xU + avgPoint1[1] * yU + avgPoint1[2] * zU + 1) * size / 2.0;
                x2 = (avgPoint2[0] * xR + avgPoint2[1] * yR + avgPoint2[2] * zR + 1) * size / 2.0;
                y2 = (avgPoint2[0] * xU + avgPoint2[1] * yU + avgPoint2[2] * zU + 1) * size / 2.0;
            }

            draw.line(x1, y1, x2, y2)
                .stroke({
                    color: lineColor,
                    width: lineWidth
                });
        }

        function drawSymbolAlongEdge(draw, edge, symbolPath, size, isChain, nodeID) {
            const start = edge.start;
            const end = edge.end;

            let x1, y1, x2, y2;

            if (Dimen == 2) {
                x1 = (start[0] + 1) * size / 2.0;
                y1 = (-start[1] + 1) * size / 2.0;
                x2 = (end[0] + 1) * size / 2.0;
                y2 = (-end[1] + 1) * size / 2.0;
            } else {
                x1 = (start[0] * xR + start[1] * yR + start[2] * zR + 1) * size / 2.0;
                y1 = (start[0] * xU + start[1] * yU + start[2] * zU + 1) * size / 2.0;
                x2 = (end[0] * xR + end[1] * yR + end[2] * zR + 1) * size / 2.0;
                y2 = (end[0] * xU + end[1] * yU + end[2] * zU + 1) * size / 2.0;
            }

            const angle = Math.atan2(y2 - y1, x2 - x1);
            const edgeLength = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);

            let centeredPath = tightenAndCenterBBox(draw, symbolPath);

            const tempPath = draw.path(centeredPath);
            const symbolBBox = tempPath.bbox();
            tempPath.remove();

            let scaleY = edgeLength * 0.8 / symbolBBox.height; // Scale to 80% of edge length
            let scaleX = isChain ? scaleY : 1; // For chain, maintain aspect ratio
            let fill = 'none';
            if (nodeID === 'ss') {
                fill = 'black';
            }
            const symbol = draw.path(centeredPath)
                .fill(fill)
                .stroke({
                    color: 'black',
                    width: 1
                });

            const scaledPath = scalePathData(centeredPath, scaleX, scaleY);
            symbol.plot(scaledPath);

            // Calculate position at 50% of the edge (between 10% and 90%)
            const centerX = x1 + (x2 - x1) * 0.5;
            const centerY = y1 + (y2 - y1) * 0.5;

            symbol.transform({
                translateX: centerX,
                translateY: centerY,
                rotate: (angle + Math.PI / 2) * 180 / Math.PI,
                originX: 'center',
                originY: 'center'
            });
        }

        while (true) {
            try {
                let s = prompt('Enter the height (in pixels) of the SVG file. This will affect size of labels. Default: 1500');
                if (s === '')
                    size = 1500;
                else
                    size = parseInt(s);
            } catch (error) {
                size = -1;
            }
            if ((size > 50) && (size < 15000))
                break;
        }

        // Set up camera and coordinate system
        const graphData = str;
        var xC = camera.position.x;
        var yC = camera.position.y;
        var zC = camera.position.z;
        var xU = camera.up.x;
        var yU = camera.up.y;
        var zU = camera.up.z;
        var xR = -(yC * zU - zC * yU);
        var yR = -(-(xC * zU - zC * xU));
        var zR = -(xC * yU - yC * xU);
        var nR = Math.sqrt(xR * xR + yR * yR + zR * zR);
        var nC = Math.sqrt(xC * xC + yC * yC + zC * zC);
        xR /= nR;
        yR /= nR;
        zR /= nR;
        xC /= nC;
        yC /= nC;
        zC /= nC;
        xU = -(yC * zR - zC * yR);
        yU = -(-(xC * zR - zC * xR));
        zU = -(xC * yR - yC * xR);

        // Create SVG for graph elements
        const drawGraph = SVG().size(size, size);
        const nodes = drawGraph.group();
        const edges = drawGraph.group();

        // Draw nodes
        graphData.objects.forEach(node => {
            let name = node.name.split('|')[0];
            let vis = false;
            for (let j = 0; j < NODES.length; j++) {
                if (name === NODES[j].id0) {
                    // Match found
                    vis = NODES[j].visible;
                    break;
                }
            }

            if (vis && (node.label.split('|')[0] !== "hidden")) {
                var x, y;
                if (Dimen == 2) {
                    x = (node.pos[0] + 1) * size / 2.0;
                    y = (-node.pos[1] + 1) * size / 2.0;
                } else {
                    x = ((node.pos[0] * xR + node.pos[1] * yR + node.pos[2] * zR) + 1) * size / 2.0;
                    y = ((node.pos[0] * xU + node.pos[1] * yU + node.pos[2] * zU) + 1) * size / 2.0;
                }
                const circle = nodes.circle(5).center(x, y).fill('white').stroke('gray');
                var text = nodes.text(node.label.split('|')[0] + '(' + node.name.split('|')[0] + ')').cx(x).cy(y);
                var fontSize = 1.5 * 1.5 * 5;
                text.font({
                    size: fontSize / 1.5 / 1.5
                });
                text.cx(x + circle.bbox().width + text.bbox().width / 2).cy(y);
            }
        });

        // Draw edges
        var arrowhead = drawGraph.marker(17, 3, function(add) {
            add.polygon('0,0 7,1.5 0,3').fill('gray');
        });
        graphData.edges.forEach(edge => {
            const start = edge.start;
            const end = edge.end;
            var x0, y0, x1, y1;
            if (Dimen == 2) {
                x0 = (start[0] + 1) * size / 2.0;
                y0 = (-start[1] + 1) * size / 2.0;
                x1 = (end[0] + 1) * size / 2.0;
                y1 = (-end[1] + 1) * size / 2.0;
            } else {
                x0 = ((start[0] * xR + start[1] * yR + start[2] * zR) + 1) * size / 2.0;
                y0 = ((start[0] * xU + start[1] * yU + start[2] * zU) + 1) * size / 2.0;
                x1 = ((end[0] * xR + end[1] * yR + end[2] * zR) + 1) * size / 2.0;
                y1 = ((end[0] * xU + end[1] * yU + end[2] * zU) + 1) * size / 2.0;
            }

            let name = str.objects[str.objects.findIndex((obj) => obj._gvid === edge.head)].name.split('|')[0];
            let vis = false;
            for (let j = 0; j < NODES.length; j++) {
                if (name === NODES[j].id0) {
                    // Match found
                    vis = NODES[j].visible;
                    break;
                }
            }
            if (vis) {
                let line;
                if (edge.gray == 1)
                    line = edges.line(x0, y0, x1, y1).stroke({
                        color: 'gray',
                        width: 0.2
                    });
                else
                    line = edges.line(x0, y0, x1, y1).stroke(edge.color).marker('end', arrowhead);

                edge.type = edge.label || 'ch';
            }
        });

        // Save graph SVG
        saveSVGToFile(drawGraph, 'graph.svg');
        addCrochetSymbolsBetweenNodes(drawGraph, graphData.objects, graphData.edges);
        saveSVGToFile(drawGraph, 'graph_with_std_crochet_symbols.svg');

        // Create SVG for crochet symbols
        const drawSymbols = SVG().size(size, size);
        addCrochetSymbolsBetweenNodes(drawSymbols, graphData.objects, graphData.edges);

        // Save crochet symbols SVG
        saveSVGToFile(drawSymbols, 'crochet_symbols.svg');
    }

    function saveSVGToFile(draw, filename) {
        const svgData = draw.svg();
        const blob = new Blob([svgData], {
            type: 'image/svg+xml'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }





    function exportGLTF() {
        var input = scene1;
        if (scene1 == null || (scene1.children.length == 0)) {
            alert('Re-run model by pressing "Show model in 3D".');
            return;
        }
        const link = document.createElement('a');
        link.style.display = 'none';
        document.body.appendChild(link); // Firefox workaround, see #6594
        function save(blob, filename) {

            link.href = URL.createObjectURL(blob);
            link.download = filename;
            link.click();

            // URL.revokeObjectURL( url ); breaks Firefox...

        }

        function saveString(text, filename) {

            save(new Blob([text], {
                type: 'text/plain'
            }), filename);

        }
        const gltfExporter = new GLTFExporter();

        //const options = {
        //    trs: params.trs,
        //    onlyVisible: params.onlyVisible,
        //    binary: params.binary,
        //    maxTextureSize: params.maxTextureSize
        //};
        //for (let i of NODES)
        //    if ('is_arrow' in i)
        //        i.visible = false
        gltfExporter.parse(
            input,
            function(result) {

                if (result instanceof ArrayBuffer) {

                    saveArrayBuffer(result, 'scene.glb');

                } else {

                    const output = JSON.stringify(result, null, 2);
                    //console.log(output);
                    saveString(output, 'scene.gltf');

                }

            },
            function(error) {

                console.log('An error happened during parsing', error);

            } //,
            //options
        );
        //while (scene1.children.length > 0) {
        //    scene1.remove(scene1.children[0]);
        // }
        //link.parentNode.removeChild(link);
    }
    //exportGLTF(scene);


    // Render the scene
    function animate() {


        requestAnimationFrame(animate);

        controls.update();

        //console.log(camera.up.x, camera.up.y, camera.up.z, camera.position, camera., XU, YU, ZU)
        if (!wasMouseDown) {

            controls.autoRotate = true; //updateCamera();;
            controls.update();
        } else {
            controls.autoRotate = false; //updateCamera();;
            controls.update();
        }





        renderer.render(scene, camera);
        //     rendererSVG.render(scene, camera);
        //     console.log(rendererSVG.domElement.outerHTML);
    }
    animate();
    return [renderer, scene, onMouseDown, onMove, handleKeyDown, handleKeyUp, STATS, handleKeyDownHide, handleKeyDownHideAnim, exportGLTF, scene1, saveSvg];
}