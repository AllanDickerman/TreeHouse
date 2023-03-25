
let ns = "http://www.w3.org/2000/svg" // store namespace
let svgDocument = null
var debug = false;
var delta_y = 12
var x_scale = 100
var num_tips = 0
on_selection_change_callback = null

create_node = function(node_id, parent_node) {
	let group = document.createElementNS(ns, "g")
	group.setAttribute("id", node_id)
	group.setAttribute("y", 0)
	group.setAttribute('bl', 0)
	group.setAttribute('depth', 0)
	group.classList.add('subtree', 'tip');
	message = "create_node("+node_id
	if (parent_node) {
		message += ", p:"+parent_node.getAttribute('id')
		parent_node.appendChild(group)
		parent_node.classList.remove('tip')
	}
	console.log(message)

	transform = svgDocument.createSVGTransform()
	group.transform.baseVal.initialize(transform);

	let circle = document.createElementNS(ns, "circle")
	circle.setAttribute('cx', '0')
	circle.setAttribute('cy', '0')
	circle.setAttribute('z', '100')
	circle.onclick=node_clicked
	circle.classList.add('clickCircle')
	group.appendChild(circle)
	return(group)
}

set_node_bl = function(node, bl) {
	console.log('set_node_bl('+node.id+", "+bl+")")
	node.setAttribute('bl', bl)
	//node.transform.baseVal[0].matrix.e = bl
}
get_node_bl = function(node) {
	//return(node.transform.baseVal[0].matrix.e)
	return(parseFloat(node.getAttribute('bl')))
}
get_node_depth = function(node) {
	return(parseFloat(node.getAttribute('depth')))
}
get_node_ypos = function(node) {
	return(node.getAttribute('y'))
}
set_node_depth = function(node) {
	var max_child_depth = 0
	for (child of node.children) {
		if (child.hasAttribute('depth')) {
			child_depth = get_node_depth(child) + get_node_bl(child)
			if (child_depth > max_child_depth)
				max_child_depth = child_depth
		}
	}
	var depth = parseFloat(node.getAttribute('bl')) + max_child_depth;
	node.setAttribute('depth', depth)
}

set_node_ordinal = function(node, ord) {
	console.log('set_node_ordinal('+node.getAttribute('id')+", "+ord)
	node.setAttribute('ordinal', ord)
}

set_node_support = function(node, value) {
	if (debug)
		console.log("set_node_support: "+node.getAttribute('id')+", "+value)
	node.setAttribute('support', value)
}

set_node_name = function(node, name) {
	console.log("set name: "+name)
	let text = document.createElementNS(ns, "text")
	text.setAttribute('dx', '5')
	text.setAttribute('dy', '3')
	var textNode = document.createTextNode(name);
	//textNode.classList.add('tipName')
	text.appendChild(textNode);
	node.appendChild(text)  
	//console.log('  new text = '+text+', tag='+text.tagName)
	//node.classList.add('tipName')
	node.setAttribute('id', name)
}

set_tip_label = function(node, field) {
	text = node.querySelector("text")
	if (text)
	{
		label = node.getAttribute('id')
		if (field != 'id') 
			label = tip_label[field][label]
		text.textContent = label
		if (debug)
			console.log("set_tip_label: "+node.getAttribute('id')+", "+field+": "+label)
	}
}

embed_node_y = function(node, delta_y) {
	//console.log("embed_node_y("+node.getAttribute('id')+", dy:"+delta_y)
	if (node.tagName != 'g')
		return
	const ypos = node.getAttribute('ordinal') * delta_y
	node.setAttribute('y', ypos)
	for (child of node.children) {
		if (child.tagName == 'circle') {
			child.setAttribute('cy', ypos);
		}
		if (child.tagName == 'text') {
			child.setAttribute('y', ypos);
		}
	}
}

embed_node_x = function(node, x_scale) {
	//console.log("embed_node_x("+node.getAttribute('id')+", p: "+node.parentNode.getAttribute('id')+", s:"+x_scale)
	if (node.tagName != 'g')
		return
	if (node.parentNode.tagName != 'g') 
		return
	path = null
	for (child of node.children) {
		if (child.tagName == 'path') {
			path = child;
		}
	}
	if (path == null) {
		path = document.createElementNS(ns, "path")
		path.classList.add('hBranch')
		node.appendChild(path)
	}
	var path_length = get_node_bl(node) * x_scale
	
	node.transform.baseVal[0].matrix.e = path_length
	d = "M0,"+get_node_ypos(node)+" h-"+path_length
	parentY = get_node_ypos(node.parentNode)
	if (parentY) {
		//deltaY = parentY - get_node_ypos(node);
		vpart = " V"+parentY
		d = d + vpart
	}
	//console.log('  path.d = '+d)
	path.setAttribute('d', d)
}

process_json_newick = function() {
	console.log("newick = "+newick)
	process_newick(newick)
	initialize_annotation(tip_label)
}

process_newick = function(nwk_string) {
	container = document.getElementById('svg_container');
	console.log("process_newick("+nwk_string.substring(0,12)+", "+container+")")
	svgDocument = document.createElementNS(ns, "svg")
	container.appendChild(svgDocument)
	if (debug)
		console.log("container and svg are: "+container+", "+svgDocument)
	svgDocument.setAttribute("id", "svgDoc")

	// set width and height
	svgDocument.setAttribute("width", "500")
	svgDocument.setAttribute('style', 'background-color: white; border: 1px solid rgb(144, 144, 144); font-size: 12px;')

	let text = document.createElementNS(ns, "text")
	text.setAttribute("x", delta_y)
	text.setAttribute("y", delta_y)
	var textNode = document.createTextNode(nwk_string);
	text.appendChild(textNode);
	svgDocument.appendChild(text)

	const nwk_len = nwk_string.length
	var nest_level = 0
	var name =''
	var bl = ''
	var name_start=-1
	var bl_start = -1
	var name_end = false
	var bl_end = false

	var cur_node = svgDocument
	var node_num = 1
	var cur_ordinal = 0
	var going_down = false
	var recent_node = null // control deciding if name is new tip or label/support for prev node
	for (var index = 0; index < nwk_len; ) {
		if (nwk_string.charAt(index) == '(') {
			//console.log("got (, nest_level="+nest_level+", :"+nwk_string.substring(index, index+15))
			// create new node
			cur_node = create_node("Node_"+node_num, cur_node)
			if (! nest_level) {
				//first node, give it an offset
				cur_node.transform.baseVal[0].matrix.e = delta_y
				cur_node.transform.baseVal[0].matrix.f = 3*delta_y
			}
			nest_level++
			node_num++
		}
		else if (nwk_string.charAt(index) == ')') {
			//console.log("got ), nest_level="+nest_level)
			nest_level--
			recent_node = cur_node.parentNode
			if (name_start >= 0) {
				name_end = true
			}
			if (bl_start >= 0) {
				bl_end = true
			}
			newly_added_tip = false
			going_down = true
		}
		else if (nwk_string.charAt(index) == ':') {
			//console.log("got :, "+nwk_string.substring(index, index+9))
			if (name_start >= 0) {
				name_end = true
			}
			bl_start = index+1
		}
		else if (nwk_string.charAt(index) == ',') {
			//console.log("got comma, nest_level="+nest_level)
			if (name_start >= 0) {
				name_end = true
			}
			if (bl_start >= 0) {
				bl_end = true
			}
			going_down = true
			recent_node = null
		}
		else if (nwk_string.charAt(index) == ';') {
			//console.log("got ;=end of tree! nest_level="+nest_level)
			//console.log('cur_node = '+cur_node.id)
			set_node_depth(cur_node)
			update_node_ordinal_from_children(cur_node);
		}
		else {
			if ((name_start == -1) & (bl_start == -1)) {
				name_start = index
				//console.log("got start of name: "+nwk_string.substring(name_start, name_start+12))
			}
		}
		if (name_end) {
			name = nwk_string.substring(name_start, index)
			nest_level++
			//console.log("got name: "+name+", level="+nest_level)
			nest_level--
			name_start = -1
			name_end = false
			if (recent_node) {
				// we have a support value for existing node
				set_node_support(recent_node, name)
				recent_node = null
			}
			else {
				var new_node = create_node(name, cur_node)
				set_node_name(new_node, name)
				set_node_ordinal(new_node, cur_ordinal)
				cur_ordinal++
				cur_node = new_node;
			}
		}
		if (bl_end) {
			bl = nwk_string.substring(bl_start, index)
			//console.log("end of bl = "+bl+", cur_node="+cur_node.id)
			bl_end=false
			bl_start = -1
			set_node_bl(cur_node, bl)
		}
		if (going_down) {
			//console.log("going down: cur_node = "+cur_node.getAttribute('id'))
			//update_node_ypos_from_children(cur_node)
			set_node_depth(cur_node)
			update_node_ordinal_from_children(cur_node)
			// go down to parent of current node
			cur_node = cur_node.parentNode
			//console.log("cur_node = "+cur_node.getAttribute('id'))
			going_down = false
		}
		index++
	}
	num_tips = cur_ordinal
	const tree_depth = get_node_depth(cur_node)
	console.log("tree_depth = "+tree_depth)
	x_scale = 400/tree_depth
	embed_tree(x_scale, delta_y)
	svgDocument.setAttribute("height", (num_tips+4)*delta_y)
	//console.log('check tree structure')
}

embed_tree = function(new_x_scale, new_delta_y, target = null) {
	x_scale = new_x_scale
	delta_y = new_delta_y
	node_elements = []
	if (target) 
		node_elements = target.querySelectorAll('.subtree')
	else
		node_elements = svgDocument.querySelectorAll('.subtree')
	for (const node of node_elements) {
		embed_node_y(node, delta_y)
	}
	for (const node of node_elements) {
		embed_node_x(node, x_scale)
	}
}

traverse_subtree = function(target) { // node on tree(g element)
	console.log("traverse_subtree( "+target.id+")");
	var visited = {};
	var done = {};
	var node = target;
	var target_id = target.getAttribute('id')
	var i = 0
	while (! done[target_id]) {
		if (i++ > 15)
			break
		node_id = node.getAttribute('id')
		if (! visited[node_id]) {
			// pre-order operations
			visited[node_id] = true
			comment = "visiting "+node_id
			if (node.hasAttribute('y'))
				comment += ", y="+get_node_ypos(node)
			console.log(comment)
		}
		var next_node = null;
		for (const child of node.children) {
			if (child.tagName == 'text') { // assume only tip nodes have a text child
				console.log(" text child="+child.id+",  visited="+ visited[child.id]+", y="+child.getAttribute('y'))
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
			done[node_id] = true;
			next_node = node.parentNode;
			console.log("going down to "+next_node.id+", done="+done[target_id])
		}
		node = next_node;
	}
	
	console.log("done traversing subtree")
}

set_tip_order = function(target, min_ord = 0) { 
	console.log("set_tip_order( "+target.id+", "+min_ord+")");
	var visited = {};
	var done = {};
	var node = target;
	var cur_ordinal = min_ord;
	while (! done[target.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			visited[node.id] = true
			console.log("visiting "+node.id)
			if (node.matches(".tip")) {
				console.log(" tip child="+node.id+",  curord="+ cur_ordinal)
				set_node_ordinal(node, cur_ordinal)
				cur_ordinal++
			}
		}
		var next_node = null;
		for (const child of node.children) {
			if (child.tagName == 'g') {
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
			update_node_ordinal_from_children(node);
			done[node.id] = true;
			next_node = node.parentNode;
			console.log("going down to "+next_node.id+", done="+done[target.id])
		}
		node = next_node;
	}
	console.log("set_tip_order done");
}

swap_descendants = function(target) { // assumes bifurcating tree (two subtrees per node)
	var firstChild = null
	var lastChild 
	console.log('swap_descendants: '+target.id)
	for (child of target.children) {
		if (child.tagName == 'g') {
			console.log('child: '+child.id+", "+child.getAttribute('ordinal'))
			if (firstChild)
				lastChild = child
			else
				firstChild = child
		}
	}
	// swap order of nodes, put last node first
	console.log("swap children: "+lastChild.getAttribute('id')+", "+firstChild.getAttribute('id'))
	target.insertBefore(lastChild, firstChild);
	for (child of target.children) 
		if (child.tagName == 'g') 
			console.log('child: '+child.id+", "+child.getAttribute('ordinal'))
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

update_node_ordinal_from_children = function(target) {// assume tip nodes have had ordinal pos set, update (fractional) ordinal pos of interior nodes
	if (target.matches('.tip')) {
		console.log("up..ord: terminal node, ordinal="+target.getAttribute('ordinal'))
		return(0)
	}
	var new_ord = 0;
	var num_children = 0;
	for (const child of target.children) {
		if (child.tagName == 'g') {
			var child_ord = parseFloat(child.getAttribute('ordinal'))
			new_ord += child_ord;
			num_children++;
			console.log(" got child_node ordinal of "+child_ord);
		}
	}
	if (! num_children) {
		console.log("No child nodes found, returning")
		return(0)
	}
	new_ord /= num_children;
	console.log("new ord calculated to be "+new_ord);
	target.setAttribute('ordinal', new_ord);
}

node_clicked=function(event) {
	target = event.target.parentNode
	action = 'highlight'
	const select = document.getElementById("node_action_select");
	if (select) {
		action = select.value;
		select.selectedIndex = 0;
	}
	console.log("node_clicked target="+target.id+", action = "+action);
	if (action == 'highlight') {
		console.log("target="+target.id+", h="+target.matches(".highlight"))
		if (target.matches(".tip")) 
			target.classList.toggle('highlight');
		else {
			//console.log("target="+target.id+", h="+target.matches(".highlight"))
			var turn_on = true //target.matches('.highlight');
			var descendant_tips = target.querySelectorAll('.tip');
			num_on = 0
			for (const node of descendant_tips) 
				if (node.matches('.highlight'))
					num_on++
			if (num_on == descendant_tips.length)
				turn_on = false
			console.log("turn-on="+turn_on+", tips="+descendant_tips.length)
			for (const node of descendant_tips) {
			   // console.log("  id="+node.id+", is_hl:"+node.matches('.highlight'))
			   if (turn_on) 
				{node.classList.add('highlight');}
			   else 
				{node.classList.remove('highlight');}
			}
		}
		if (on_selection_change_callback) { 
		   var selected_tip_id_list = [];
		   tip_elements = document.querySelectorAll('.tip');
		   for (const tip of tip_elements) {
			if (tip.matches('.highlight')) { selected_tip_id_list.push(tip.id); }
		   }
		   //on_selection_change_callback(selected_tip_id_list); 
		}
	}
	else if (action == 'reroot') {root_below_node(target);}
	else if (action == 'order_tree') {orderTree();}
	else if (action == 'newick') {generate_newick(target);}
	else if (action == 'swap') {
		console.log("try swapping nodes: "+target.id);
		const min_ord = get_node_min_ord(target)
		swap_descendants(target);
		set_tip_order(target, min_ord)
		embed_tree(x_scale, delta_y, target)
		for (child of target.children) 
			if (child.tagName == 'g') 
				console.log('xild: '+child.id+", "+child.getAttribute('ordinal'))
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
	else if (action == 'list_highlighted') {
		highlighted_tips = svgDocument.querySelectorAll(".highlight");
		for (tip of highlighted_tips)
			console.log(tip.id)
	}
}

get_node_min_ord = function(node) {
	tip_elements = node.querySelectorAll('.tip')
	min_ord = num_tips
	for (tip of tip_elements) 
		if (tip.getAttribute('ordinal') < min_ord)
			min_ord = tip.getAttribute('ordinal')
	return(min_ord)
}

highlight_taxon = function(target_taxon_id) {
   console.log('highglight_taxon('+target_taxon_id)
   h_elements = document.querySelectorAll('.highlight')
   for (h of h_elements)
	h.classList.remove('highlight')
   tip_elements = document.querySelectorAll('.tip');
   var tips_in_taxon = [];
   for (const tip of tip_elements) {
	taxon = tip_label['taxon'][tip.getAttribute('id')]
	i = 0;
	while (taxon ) {
		if (taxon == target_taxon_id) {
			tips_in_taxon.push(taxon);
			tip.classList.add('highlight')
			console.log("tip "+tip.getAttribute('id') +", is in taxon "+taxon)
			break
		}
		i++
		if (i > 10)
			break
		taxon = taxon_parent[taxon];
	}
   }
}


initialize_annotation = function()
{
	if (debug)
		console.log("initialize_annotation");
	var select = document.getElementById("annotation_field_select");
	if (select) {
	    for(const field in tip_label) {
		    if (debug)
			    console.log("annotation field "+field);
		var option = document.createElement('option');
		option.text = option.value = field;
		select.add(option, 0);
	    }
	    var option = document.createElement('option');
	    option.text = option.value = 'id';
	    select.add(option, 0);
	    var starting_label = 'id';
	    if (tip_label['genome_name']) 
		starting_label = 'genome_name';
	    if (debug) {
		    console.log('tip_label[genome_name] = '+tip_label['genome_name'])
		    console.log('starting_label = '+starting_label)
	    }
	    select.value=starting_label;
	    select.onchange=function(){relabel_tips(this.value)};
	    relabel_tips(starting_label);
	}
}

relabel_tips = function(field) {
    console.log("function relabel_tips "+field);
    tip_elements = document.querySelectorAll('.tip');
	if (debug)
		console.log("tips: "+tip_elements.length)
    for (const tip of tip_elements) {
        set_tip_label(tip, field);
    }
}

root_below_node = function(target) {
	console.log("root_below_node "+target.id+", t"+target);
	// find path to root
	var node = target;
	var path_to_root = [];
	while (node != svgDoc) {
		path_to_root.push(node);
		console.log("ptr "+node.id+", par:"+node.parentNode.id);
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
		newSubtree = create_node("new_root")
		//newSubtree = document.createElementNS('http://www.w3.org/2000/svg', 'g');
		//newSubtree.id = "resolve_basal_tritomy";
		newSubtree.classList.remove('tip');
		for (nonpath_child of root_nonpath_children) {
			newSubtree.appendChild(nonpath_child);
		}
		//var matrix = svgDocument.createSVGMatrix();
		//newSubtree.transform.baseVal.initialize(svgDocument.createSVGTransform());
		//const hPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
		//hPath.setAttribute('d', 'M0,0 h0.5');
		//hPath.classList.add('hBranch');
		//newSubtree.appendChild(hPath);
		//const vPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
		//vPath.setAttribute('d', 'M0,0 v0.5');
		//vPath.classList.add('vBranch');
		//newSubtree.appendChild(vPath);
		//const clickCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
		//clickCircle.classList.add('clickCircle');
		//clickCircle.setAttribute('onclick', 'node_clicked(this.parentNode)');
		//newSubtree.appendChild(clickCircle);
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
		var base_node_bl = get_node_bl(base_node);
		var outer_node_bl = get_node_bl(outer_node);
		console.log("set outer_node bl to "+(outer_node_bl + base_node_bl))
		set_node_bl(outer_node, (outer_node_bl + base_node_bl));
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
	var root_branch_length = get_node_bl(target);
	set_node_bl(target, root_branch_length/2);
	set_node_bl(outer_node, root_branch_length/2);
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
		set_node_bl(target, longer);
		set_node_bl(outer_node, shorter);
	}
	else {
		set_node_bl(target, shorter);
		set_node_bl(outer_node, longer);
	}
	if (debug) console.log("target_length = "+get_node_bl(target))

	set_tip_order(root);
	embed_tree(x_scale, delta_y)
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
					var r = radius[child.id] + get_node_bl(child);
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

