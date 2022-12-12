console.log("reading svg_tree.js");

var svgDocument;
var annotation = {};
var debug = true;
window.onload = function () {
    	console.log("onload");
	svgDocument = document.querySelector('svg');
	console.log("svgDocument = ", svgDocument);
    	if (annotation) {
	    if (debug)
		console.log("annotation fields: ");
	    var select = document.getElementById("annotation_field_select");
	    for(const field in annotation) {
		    if (debug)
			    console.log("annotation field "+field);
		var option = document.createElement('option');
		option.text = option.value = field;
		select.add(option, 0);
	    }
	    var option = document.createElement('option');
	    option.text = option.value = 'genome_id';
	    select.add(option, 0);
	    var starting_label = 'genome_id';
	    if (annotation['genome_name']) 
		starting_label = 'genome_name';
	    if (debug) {
		    console.log('annotation[genome_name] = '+annotation['genome_name'])
		    console.log('starting_label = '+starting_label)
	    }
	    select.value=starting_label;
	    select.onchange=function(){relabel_tips(this.value)};
	    relabel_tips(starting_label);
    }
};

var on_selection_change_callback = 1;
set_on_selection_change_callback=function(callback) {
       on_selection_change_callback = callback;
   }
show_id_list_to_console=function(id_list) {
         console.log("Selected IDs: "+id_list.join());
   }
   set_on_selection_change_callback(show_id_list_to_console);

relabel_tips = function(field) {
    console.log("function relabel_tips "+field);
    tip_elements = document.querySelectorAll('.tipName');
    for (const tip of tip_elements) {
        tip.innerHTML = (field == 'genome_id' ? tip.id : annotation[field][tip.id]);
    }
}
restore_ids = function() {
    console.log("function resotore_ids");
    tip_elements = document.querySelectorAll('.tipName');
    for (const tip of tip_elements) {
        tip.innerHTML = tip.id;
    }
}

global_action=function() {
	var select = document.getElementById("global_action_select");
	var action = select.value;
	if (action == 'global_action')
		return;
	console.log("global action: "+action);
	select.selectedIndex = 0;
	if (action == 'order_tree_up') {
		orderTree();
	}
	else if (action == 'generate_newick') {
		generate_newick();
	}
	else if (action == 'save_arrangement') {
		save_arrangement();
	}
	else if (action == 'generate_json_newick') {
		generate_json_newick();
	}
}

generate_json_newick = function() {
}
flag_tree_taxon = function(tree_id, taxon_id) {
	console.log("flag_tree_taxon("+tree_id+", "+taxon_id+")")
	fetch('http://127.0.0.1:8080/flag_tree_taxon?tree_id='+tree_id+"&taxon_id="+taxon_id)
}

save_arrangement = function() {
	nwk = generate_newick(null, true);
	tree_id = document.getElementById("tree_id").innerHTML;

	const data = { 'tree_id': tree_id,
	'nwk' : nwk};
	console.log("in save_arrangment(): data= "+JSON.stringify(data));
	fetch('http://127.0.0.1:8080/save_arranged_tree', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(data)
	})
	.then((response) => response.json())
	.then((data) => {
	console.log('Success:', data);
	})
	.catch((error) => {
	console.error('Error:', error);
	});
}

node_clicked=function(target) {
	const select = document.getElementById("node_action_select");
	const action = select.value;
	console.log("node_clicked target="+target.id+", action = "+action);
	if (action == 'highlight') {
		console.log("target="+target.id+", hTrans="+target.transform.baseVal[0].matrix.e + ", p="+target.parentNode.id)
		target.classList.toggle('highlight');
		var turn_on = target.matches('.highlight');
		var affected_nodes = target.querySelectorAll('.tipName, .subtree, .tip');
		for (const node of affected_nodes) {
		   // console.log("  id="+node.id+", is_hl:"+node.matches('.highlight'))
		   if (turn_on) 
			{node.classList.add('highlight');}
		   else 
			{node.classList.remove('highlight');}
		}
		if (on_selection_change_callback != 1) { 
		   var selected_tip_id_list = [];
		   tip_elements = document.querySelectorAll('.tipName');
		   for (const tip of tip_elements) {
			if (tip.matches('.highlight')) { selected_tip_id_list.push(tip.id); }
		   }
		   on_selection_change_callback(selected_tip_id_list); 
		}
	}
	else if (action == 'reroot') {root_below_node(target);}
	else if (action == 'order_tree') {orderTree();}
	else if (action == 'newick') {generate_newick(target);}
	else if (action == 'swap') {
		console.log("try swapping nodes: "+target.id);
		swap_descendants(target);
		var minY = getNodeMinY(target);
		set_descendant_ypos(target, minY);
	}
	select.selectedIndex = 0;
}

swap_descendants = function(target) { // assumes bifurcating tree (two subtrees per node)
	var child_nodes = [];
	for (child of target.children) {
		if (child.tagName == 'g') {
			child_nodes.push(child);
		}
	}
	// swap order of nodes
	target.insertBefore(child_nodes[1], child_nodes[0]);
}

update_node_ypos = function(target) {// assume text elements have had ypos set, update ypos of g elements and children in post-order traverse
	// update_yvals(base_node);
	var hBranch;
	var vBranch;
	var clickCircle;
	var child_positions = [];
	console.log("update_node_ypos for node "+target.id);
	for (const child of target.children) {
		if (child.tagName == 'text') {
			var child_ypos = child.y.baseVal[0].value;
			child_positions.push(child_ypos);
			console.log(" got text element ypos of "+child_ypos);
		}
		else if (child.tagName == 'circle') {
			clickCircle = child;
		}
		else if (child.tagName == 'g') {
			var child_ypos = parseFloat(child.getAttribute('y'))
			child_positions.push(child_ypos);
			console.log(" got child_node ypos of "+child_ypos);
		}
		else if (child.matches('.vBranch')) {
			vBranch = child;
		}
		else if (child.matches('.hBranch')) {
			hBranch = child;
		}
	}
	var new_ypos = 0;
	var min_child_ypos = child_positions[0];
	var max_child_ypos = min_child_ypos;
	console.log("child_positions = "+child_positions);
	for (var p of child_positions) {
		new_ypos += p;
		if (p < min_child_ypos) {
			min_child_ypos = p;
		}
		else if (p > max_child_ypos) {
			max_child_ypos = p;
		}
	}
	new_ypos /= child_positions.length;
	console.log("new ypos calculated to be "+new_ypos);
	target.setAttribute('y', new_ypos);
	// now update position of vertical branch (uniting child nodes)
	if (vBranch) {
		var d = "M0,"+min_child_ypos.toFixed(4)+" v"+(max_child_ypos-min_child_ypos).toFixed(4);
		vBranch.setAttribute("d", d);
		console.log("  vBranch for "+target.id+" = "+d);
	}
	if (hBranch) {
		var d = hBranch.getAttribute("d");
		console.log("  hBranch.d = "+hBranch.getAttribute("d"));
		d_parts = d.split(' ');
		d_parts[0] = "M0,"+new_ypos.toFixed(4);
		d = d_parts.join(" ");
		hBranch.setAttribute("d", d);
	}
	if (clickCircle) {
		clickCircle.setAttribute('cy', new_ypos);
	}
	console.log(" done");
}

set_branch_length=function(target, new_length) {
	console.log("set_branch_length of "+target.id+" to "+new_length)
	var xform = target.transform.baseVal[0]; // An SVGTransformList
	xform.setTranslate(new_length, 0);
	for (child of target.children) {
		if (child.matches('.hBranch')) { 
			var d = child.getAttribute("d");
			console.log(" hBranch.d = "+d);
			d = d.replace(/h.*/, "h-"+new_length);
			child.setAttribute("d", d);
			break;
		}
	}
}

getNodeMinY=function(target) {
	console.log("getNodeMinY() " + target.id);
	var yvals = [];
	var min_ypos = 1e6;
	// traverse subtree
	var visited = {};
	var done = {};
	var node = target;
	while (! done[target.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			// console.log("visit node "+node.id);
			visited[node.id] = true
		}
		var next_node = null;
		for (const child of node.children) {
			//console.log(" child="+child.id+", tagName="+child.tagName+", visited="+visited[child.id])
			if (child.tagName == 'g' && ! visited[child.id]) {
				next_node = child;
				console.log("child node = "+child.id);
				break;
			}
			else if (child.tagName == 'text') {
				var y = child.y.baseVal[0].value;
				yvals.push(y);
				if (y < min_ypos) {
					min_ypos = y;
				}
				console.log("got tip: "+child.id+", y="+y+", minypos="+min_ypos);
			}
		}
		if (!next_node) {
			// post-order operations
			done[node.id] = true;
			next_node = node.parentNode;
		}
		node = next_node;
	}
	console.log("yvals: "+yvals);
	return(min_ypos);
}

var delta_y = 15; // vertical spacing between tips on tree

set_descendant_ypos = function(target, next_y) { // node on tree(g element) and next_y is to be assiged to the first (upper-most) tip
	console.log("set_descendant_ypos( "+target.id+", "+next_y+")");
	if (! next_y) next_y = delta_y;
	var visited = {};
	var done = {};
	var node = target;
	while (! done[target.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			visited[node.id] = true
			console.log("visiting "+node.id)
		}
		var next_node = null;
		for (const child of node.children) {
			if (child.tagName == 'text') { // assume only tip nodes have a text child
				console.log(" text child="+child.id+",  visited="+ visited[child.id]+", y="+child.getAttribute('y'))
				child.setAttribute('y', next_y);
				next_y += delta_y;
				break;
			}
			else if (child.tagName == 'g') {
				if (! visited[child.id]) {
					next_node = child;
					console.log("going up to "+next_node.id)
					break;
				}
			}
		}
		if (!next_node) {
			// post-order operations
			//console.log("about to update node ypos for node "+node.id);
			update_node_ypos(node);
			done[node.id] = true;
			next_node = node.parentNode;
			console.log("going down to "+next_node.id+", done="+done[target.id])
		}
		node = next_node;
	}
	while (! node.matches('.tree_container')) {
		update_node_ypos(node);
		node = node.parentNode;
	}
	
	console.log("set_descendant_ypos done, returning "+next_y);
	return(next_y);
}

root_below_node = function(target) {
	console.log("root_below_node "+target.id);
	// find path to root
	var node = target;
	var path_to_root = [];
	while (! node.matches('.tree_container')) {
		path_to_root.push(node);
		node = node.parentNode;
	}
	const container = node;
	var ptr = "";
	for (p of path_to_root)
		ptr += ", "+p.id;
	console.log("path to root = "+ptr);
	const root = path_to_root.pop();
	console.log("root = "+root.id);
	// disconnect root
	var root_nonpath_children = [];
	var base_node = path_to_root.pop(); // possibly is target node
	//var reference_node = base_node.children[0]; // default is to insert outer_node as first child of base
	var insertFirst; // all node insertions will be either first (if true) or last (if false)
	for (var child of root.children) {
		if (child.tagName == 'g') {
			if (child == base_node) {
				if ( !root_nonpath_children.length ) {  // base_node seen before any other child, insert first 
					insertFirst = true; // meaning outer_node comes first, other_node will be inserted as last child of base_node
				}
			}
			else {
				root_nonpath_children.push(child);
				insertFirst = false;
			}
		}
	}
	console.log("insertFirst = "+insertFirst)
	var outer_node;
	var newSubtree;
	if (root_nonpath_children.length == 1) {
		outer_node = root_nonpath_children[0];
	}
	else {
		console.log("number of root non-path children = "+root_nonpath_children.length)
		newSubtree = document.createElementNS('http://www.w3.org/2000/svg', 'g');
		newSubtree.id = "resolve_basal_tritomy";
		newSubtree.classList.add('subtree');
		for (nonpath_child of root_nonpath_children) {
			newSubtree.appendChild(nonpath_child);
		}
		//var matrix = svgDocument.createSVGMatrix();
		newSubtree.transform.baseVal.initialize(svgDocument.createSVGTransform());
		const hPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
		hPath.setAttribute('d', 'M0,0 h0.5');
		hPath.classList.add('hBranch');
		newSubtree.appendChild(hPath);
		const vPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
		vPath.setAttribute('d', 'M0,0 v0.5');
		vPath.classList.add('vBranch');
		newSubtree.appendChild(vPath);
		const clickCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
		clickCircle.classList.add('clickCircle');
		clickCircle.setAttribute('onclick', 'node_clicked(this.parentNode)');
		newSubtree.appendChild(clickCircle);
		console.log(" children of new subtree: ");
		for (var child of newSubtree.children) {
			console.log(child.tagName+": "+child.className.baseVal);
			for (var name in child)  
				if (child.hasOwnProperty(name))
					console.log("   "+name+": "+child[name]);
			console.log(' expl: class:' + child['className'])
		}
		outer_node = newSubtree;
	}
	var reference_node = insertFirst ? base_node.children[0] : null;
	base_node.insertBefore(outer_node, reference_node); 
	var iteration = 1;
	// now everything is connected through base_node, find next outer_node and upper_node and shift them
	while (base_node != target) {
		var ptr = "";
		for (p of path_to_root)
			ptr += ", "+p.id;
		console.log("path to root = "+ptr);
		console.log("base="+base_node.id+", outer="+outer_node.id)
		var base_node_bl = get_branch_length(base_node);
		var outer_node_bl = get_branch_length(outer_node);
		console.log("set outer_node bl to "+(outer_node_bl + base_node_bl))
		set_branch_length(outer_node, (outer_node_bl + base_node_bl));
		if (iteration > 1)
			outer_node.removeChild(base_node);
		reference_node = insertFirst ? base_node.children[0] : null;
		base_node.insertBefore(outer_node, reference_node);
		var upper_node = path_to_root.pop();
		// upper node is one on path_to_root and will become the next base
		outer_node = base_node;
		base_node = upper_node;
		iteration += 1;
	}
	// now base node is target
	console.log("base_node is "+base_node.id);
	var root_branch_length = get_branch_length(target);
	set_branch_length(target, root_branch_length/2);
	set_branch_length(outer_node, root_branch_length/2);
	root.insertBefore(outer_node, null);
	reference_node = insertFirst ? outer_node : null;
	root.insertBefore(target, reference_node);
	const radius = find_radius_of_subtrees(root);
	if (debug)
		console.log("root bl: "+root_branch_length+", vs tr:"+radius[target.id]+", or: "+radius[outer_node.id]);
	// see how we might want to allocate available root branch length to longer vs shorter side
	const to_diff = radius[target.id] - radius[outer_node.id];
	if (debug) console.log("to_diff = "+to_diff)
	var shorter = 0.01 * radius[root.id]; // fixed small proportion of tree depth
	if (Math.abs(to_diff) < root_branch_length) {
		shorter = (root_branch_length - Math.abs(to_diff))/2;
	}
	else if (Math.abs(to_diff) < shorter) {
		shorter = 0;
	}
	const longer = root_branch_length - shorter;
	if (debug) console.log("longer = "+longer+", shorter = "+shorter)

	if (to_diff < 0) {
		set_branch_length(target, longer);
		set_branch_length(outer_node, shorter);
	}
	else {
		set_branch_length(target, shorter);
		set_branch_length(outer_node, longer);
	}
	if (debug) console.log("target_length = "+get_branch_length(target))

	set_descendant_ypos(root, delta_y);
	console.log("done re-rooting");
	if (debug & newSubtree) {
		console.log("newSubtree: "+newSubtree.id+" hTrans="+newSubtree.transform.baseVal[0].matrix.e)
		for (var child of newSubtree.children) {
			console.log(child.tagName+": "+child.className.baseVal+", id="+child.id);
			if (child.tagName == 'path') 
				console.log("   path d="+child.getAttribute('d'));
			var box = child.getBoundingClientRect();
			console.log("   bb: "+box.left+", "+box.top+", "+box.right+", "+box.bottom);
		}
	}
}

get_branch_length = function(target) {
	var xform = target.transform.baseVal[0]; // An SVGTransformList
	var bl = xform.matrix.e;
	console.log("get_branch_length("+target.id+") = "+bl);
	return(bl);
}


generate_newick=function(target, use_id=false) {
	if (! target)
		target = getRoot();
	console.log("write_tree_as_newick(" + target.id+", "+use_id+")");
	var retval = '';
	// traverse subtree
	var visited = {};
	var done = {};
	var node = target;
	var first_child = true;
	while (! done[target.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			if (debug) console.log('pre-order on '+node.id);
			if (!node.matches('.tip')) {
				retval += "(";
			}
			visited[node.id] = true
		}
		else {
			if (debug) console.log("re-visit "+node.id);
		}
		var next_node = null;
		for (const child of node.children) {
			if (child.matches('.subtree')) {
				//if (debug) console.log(" child="+child.id+", tagName="+child.tagName+", visited="+visited[child.id]);
				if ( ! visited[child.id]) {
					if (! first_child) {retval += ',';} //we have been at this node before, need a comma
					next_node = child;
					first_child = true;
					if (debug) console.log("go up to child node = "+child.id);
					break;
				}
			}
			else if (child.tagName == 'text') {
				if (debug) console.log("got tip: "+child.id+", label="+child.innerHTML);
				retval += use_id ? child.id : child.innerHTML;
			}
		}
		if (!next_node) {
			// post-order operations
			if (!node.matches('.tip')){
				retval += ')'; 
			}
			var bl = get_branch_length(node);
			if (bl) {
				retval += ':'+bl.toFixed(5);
			}
			if (debug) console.log('done with '+node.id);
			done[node.id] = true;
			first_child = false;
			next_node = node.parentNode;
		}
		node = next_node;
	}
	retval += ';';
	console.log("write_tree_as_newick: "+retval);
	return(retval);
}

find_radius_of_subtrees=function(target) {
	// define radius as the longest directed path from an interior node to any of its descendant tips
	// this contrasts to 'diameter' which is the sum of the two longest radii
	if (! target)
		target = getRoot();
	console.log("find_diameter_of_subtree() " + target.id);
	var radius = {};
	// traverse subtree
	var visited = {};
	var done = {};
	var node = target;
	while (! done[target.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			visited[node.id] = true
		}
		var next_node = null;
		var longest_child_radius = 0;
		for (const child of node.children) {
			if (child.matches('.subtree')) {
				//console.log(" child="+child.id+", tagName="+child.tagName+", visited="+visited[child.id])
				if ( visited[child.id]) {
					var r = radius[child.id] + get_branch_length(child);
					if (r > longest_child_radius)
						longest_child_radius = r;
				}
				else {
					next_node = child;
					//console.log("go up to child node = "+child.id);
					break;
				}
			}
			else if (child.tagName == 'text') {
				//console.log("got tip: "+child.id+", label="+child.innerHTML);
				longest_child_radius = 0;
				break;
			}
		}
		if (!next_node) {
			// post-order operations
			radius[node.id] = longest_child_radius;
			console.log('  radius of '+node.id+' = '+radius[node.id]);
			done[node.id] = true;
			next_node = node.parentNode;
		}
		node = next_node;
	}
	console.log("found radius of each node");
	return(radius);
}

getRoot=function() {
	var container = document.querySelector(".tree_container");
	var root = container.children[0];
	return root;
}

orderTree=function(larger_subtrees_up=false) {
	console.log("orderTree() larger_subtrees_up = " + larger_subtrees_up);
	var num_descendants = {};
	var visited = {};
	var done = {};
	var root = getRoot();
	var node = root;
	// traverse subtree
	while (! done[root.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			// console.log("visit node "+node.id);
			visited[node.id] = true
			num_descendants[node.id] = 0;
		}
		var next_node = null;
		var sum_of_child_descendants = 0;
		for (const child of node.children) {
			//console.log(" child="+child.id+", tagName="+child.tagName+", visited="+visited[child.id])
			if (child.tagName == 'g') {
				if (visited[child.id]) {
					sum_of_child_descendants += num_descendants[child.id];
				}
				else {
					next_node = child;
					//console.log("child node = "+child.id);
					break;
				}
			}
			else if (child.tagName == 'text') {
				sum_of_child_descendants = 1;
				//console.log("got tip: "+child.id);
			}
		}
		if (!next_node) {
			// post-order operations
			num_descendants[node.id] = sum_of_child_descendants;
			done[node.id] = true;
			next_node = node.parentNode;
		}
		node = next_node;
	}
	console.log("counted descendants for each node");
	var all_nodes = document.querySelectorAll(".subtree");
	var any_changed = false;
	for (var node of all_nodes) {
		var child_num_descendants = [];
		for (var child of node.children) 
			if (child.matches('.subtree'))
				child_num_descendants.push(num_descendants[child.id]);
		if (child_num_descendants[0] < child_num_descendants[1]) {
			swap_descendants(node);
			any_changed = true;
		}
	}
	if (any_changed)
		set_descendant_ypos(root, delta_y);
	return;
}
