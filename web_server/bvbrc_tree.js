const ns = "http://www.w3.org/2000/svg" // store namespace
let svgDocument = null
let delta_y = 12
let x_scale = 100
let num_tips = 0 // number of tips on the tree
let node_num = 0 // number of nodes in the tree
let stop_rank = ''; 
let debug = 0
let annotation = null;

console.log("loading bvbrc_tree.js")

get_root = function() {
	return svgDocument.querySelector('.subtree')
}
process_json_newick = function() {
	console.log("newick = "+newick)
	create_tree(newick)
	initialize_annotation(tip_label)
}

create_tree = function(nwk_string, input_annotation=null, annotation_labels=null, initial_label=null) {
	container = document.getElementById('svg_container');
	console.log("create_bvbrc_tree:"+nwk_string.substring(0,12))
	if (stop_rank & debug)
		console.log("stop_rank="+stop_rank)
	svgDocument = document.createElementNS(ns, "svg")
	container.appendChild(svgDocument)
	svgDocument.setAttribute("id", "svgDoc")
	newick = nwk_string 

	// set width and height
	svgDocument.setAttribute("width", "800")
	svgDocument.setAttribute('style', 'background-color: white; border: 1px solid rgb(144, 144, 144); font-size: 12px;')
	//debugger
	//const stylesheet = new CSSStyleSheet();
	const stylesheet = document.createElementNS(ns, 'style');
	svgDocument.appendChild(stylesheet);
	let sheets = document.styleSheets;
    	let sheet;
	for(var i=0, length=sheets.length; i<length; i++){
	   sheet=sheets.item(i);
	   if (sheet.ownerNode == stylesheet) i
		break;
	}
	sheet.insertRule(".highlight{fill:red;}", 0);
	sheet.insertRule("circle{r: 5; fill: red; opacity: 0.0; cursor: pointer}", 0);
	sheet.insertRule(".tip{font-family: Arial, sans-serif; font-size: 10px; fill: blue}", 0);
	//sheet.insertRule("circle.tip{fill: orange}", 0);
	sheet.insertRule("circle.taxon{fill: red}", 0);
	sheet.insertRule("circle.tip{fill: orange}", 0);
	sheet.insertRule(".branch{file: none; stroke-width: 2.5; stroke black}", 0);

	for (let i = 0; i < sheet.cssRules.length; i++) {
		console.log(sheet.cssRules[i])
	}
	//let textNode = document.createTextNode(newick);
	//text.appendChild(textNode);
	//svgDocument.appendChild(text)
	
	const nwk_len = newick.length
	let nest_level = 0

	let cur_node = svgDocument
	num_tips = 0
	node_num = 0
	let going_down = false
	parse_newick(0, nwk_len, svgDocument)
	const root = get_root()
	root.transform.baseVal[0].matrix.e = delta_y
	root.transform.baseVal[0].matrix.f = 3*delta_y
	let tree_depth = get_node_depth(root)
	console.log("tree_depth = "+tree_depth)
	if (tree_depth == 0) {
		tree_depth = 600
		console.log("tree_depth is zero!!!, set to 600")
	}
	orderTree();
	x_scale = 800/tree_depth
	embed_tree_y()
	embed_tree_x()
	svgDocument.setAttribute("height", (num_tips+4)*delta_y)
	//container.setAttribute("height", (num_tips+4)*delta_y)
	resizeTreeContainer()
	window.onresize = resizeTreeContainer;
	//console.log('check tree structure')
	if (input_annotation) {
		console.log("input annotation provided")
		annotation = input_annotation
	}
	if (annotation_labels) {
		//create empty slots in annotation that can be retrieved later
		console.log("annotation_labels = "+annotation_labels)
		console.log("type of annotation_labels = "+(typeof annotation_labels))
		console.log("stubs for annotation: num="+annotation_labels.length);
		for (i in [1,2,3,4,5]) {
			console.log("stub: "+annotation_labels[i])
		}
		if (! annotation) {
			annotation = []
		}
		for (const label in annotation_labels) {
			annotation[label] = null
		}
	}
	console.log("initial label: "+initial_label)
	initialize_annotation(initial_label)

}

function resizeTreeContainer(e) {
	var height = 0;
	var body = window.document.body;
	if (window.innerHeight) {
		height = window.innerHeight;
	} else if (body.parentElement.clientHeight) {
		height = body.parentElement.clientHeight;
	} else if (body && body.clientHeight) {
		height = body.clientHeight;
	}
	container = document.getElementById('svg_container');
  	container.style.height = ((height - container.offsetTop) + "px");
}

create_node = function(node_id, parent_node, node_label='', branch_length=0, node_support=0) {
	const group = document.createElementNS(ns, "g")
	group.setAttribute("id", node_id)
	group.setAttribute("y", 0)
	group.setAttribute('bl', branch_length)
	group.setAttribute('depth', 0)
	group.setAttribute('label', node_label)
	group.setAttribute('support', node_support)
	group.classList.add('subtree');
	message = "create_node("+node_id
	if (parent_node) {
		message += ", p:"+parent_node.getAttribute('id')
		parent_node.appendChild(group)
		parent_node.classList.remove('tip')
	}
	if (debug > 1)
		console.log(message)

	transform = svgDocument.createSVGTransform()
	group.transform.baseVal.initialize(transform);

	let circle = document.createElementNS(ns, "circle")
	circle.setAttribute('cx', '0')
	circle.setAttribute('cy', '0')
	circle.setAttribute('z', '-1') 
	circle.onclick=node_clicked
	circle.classList.add('clickCircle')
	group.appendChild(circle)

	path = document.createElementNS(ns, "path")
	path.classList.add('branch')
	group.appendChild(path)
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
set_node_depth_from_children = function(node) {
	let max_child_depth = 0
	if (! node.matches('.tip')) {
		for (child of node.children) {
			if (child.hasAttribute('depth')) {
				child_depth = get_node_depth(child) + get_node_bl(child)
				if (child_depth > max_child_depth)
					max_child_depth = child_depth
			}
		}
		//if (max_child_depth == 0)
		//	throw("Hey, max child depth is 0 in set_node_depth_from_children!")
	}
	let depth = parseFloat(node.getAttribute('bl')) + max_child_depth;
	node.setAttribute('depth', depth)
	if (debug > 1) {
		console.log("set_node_depth_from_children("+node.getAttribute('id')+")\nmax_child_depth="+max_child_depth+", depth="+depth)
	}
}

set_node_ordinal = function(node, ord) {
	//console.log('set_node_ordinal('+node.getAttribute('id')+", "+ord)
	node.setAttribute('ordinal', ord)
}

set_node_support = function(node, value) {
	if (debug)
		console.log("set_node_support: "+node.getAttribute('id')+", "+value)
	node.setAttribute('support', value)
}

set_node_label_vis = function(node, is_tip) { 
	let label = node.getAttribute('label')
	if (debug > 1)
		console.log("set label: "+label+", is_tip="+is_tip)
	if (label.length == 0)
		return // no label
	let element_type = is_tip ? "text" : "title"
	let labelDisplay = document.createElementNS(ns, element_type)
	labelDisplay.setAttribute('dx', '5')
	labelDisplay.setAttribute('dy', '3')
	let textNode = document.createTextNode(node.getAttribute('label'));
	labelDisplay.appendChild(textNode);
	let circle = node.querySelector('circle')
	if (is_tip) {
		node.classList.add('tip');
		//circle.classList.add('tip')
		node.appendChild(labelDisplay)  
	}
	else {
		node.classList.remove('tip');
		circle.appendChild(labelDisplay)  
		circle.classList.add('taxon')
	}
}

set_tip_text = function(node, display_text) {
	text = node.querySelector("text")
	text.textContent = display_text
}

async function relabel_tips(field) {
	if (debug)
    		console.log("function relabel_tips "+field);
	if (annotation[field] == null) {
		// data hasn't been loaded, fetch it
		//const url = server_url + "getTreeAnnotation?tree="+tree_id+"&field="+field
		const url = "getTreeAnnotation?tree="+tree_id+"&field="+field
		console.log("try fetching "+url)
		if (debug)
			console.log("fetching "+field+" for tree "+tree_id+": "+url);
		const response = await fetch(url);
		annotation[field] = await response.json();
		if (debug)
			console.log(annotation[field]);
	}
    	tip_elements = document.querySelectorAll('.tip');
    	for (const tip of tip_elements) {
		const tip_id = tip.getAttribute('id')
		let label = annotation[field][tip_id]
        	set_tip_text(tip, label);
    	}
}

show_node_info = function(node) {
	console.log("show_node_info "+node.id)
	if (node.hasAttribute('label'))
		console.log('label = '+node.getAttribute('label'))
	if (node.hasAttribute('bl'))
		console.log('bl = '+node.getAttribute('bl'))
	if (node.hasAttribute('support'))
		console.log('support = '+node.getAttribute('support'))
}

embed_node_y = function(node) {
	//console.log("embed_node_y("+node.getAttribute('id')+", dy:"+delta_y)
	if (node.tagName != 'g')
		return
	const ypos = node.getAttribute('ordinal') * delta_y
	if (debug > 2) {
		message = "embed_node_y(), id="+node.getAttribute('id')+", dy:"+delta_y+", ypos:"+ypos+")"
		console.log(message)
	}
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

embed_node_x = function(node) {
	if (debug > 2) {
		console.log("embed_node_x("+node.getAttribute('id')+", p: "+node.parentNode.getAttribute('id')+", s:"+x_scale)
	}
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
		return
	}
	let path_length = get_node_bl(node) * x_scale
	
	node.transform.baseVal[0].matrix.e = path_length
	d = "M0,"+get_node_ypos(node)+" h-"+path_length
	parentY = get_node_ypos(node.parentNode)
	if (parentY) {
		vpart = " V"+parentY
		d = d + vpart
	}
	//console.log('  path.d = '+d)
	path.setAttribute('d', d)
}


expand_node = function(head_node) {
	let start = head_node.getAttribute("newick_start")
	let end = head_node.getAttribute("newick_end")
	parse_newick(start, end, head_node)
	set_node_label_vis(head_node, false) // show taxon label for tips, tooltip otherwise
	update_node_ordinal_from_children(head_node)
	const root = get_root()
	const tree_depth = get_node_depth(root)
	console.log("tree_depth = "+tree_depth)
	x_scale = 400/tree_depth
	//debugger
	set_tip_order(root, 0)
	embed_tree_y()
	embed_tree_x()
	svgDocument.setAttribute("height", (num_tips+4)*delta_y)
}

parse_newick = function(start, end, start_node) {
	// read from global newick string
	//debugger
	console.log("parse_newick("+start+", "+end)
	num_tips // global 
	node_num // global
	let going_down = false
	let cur_node = start_node
	let nest_level = 0
	let prev_i = start - 1
	for (let index = start; index < end; index++) {
		const tree_char = newick.charAt(index)
		if (index <= prev_i) {
			debugger
			throw("index is too low")
		}
		prev_i = index
		if (tree_char == ')') {
			if (debug > 1) 
				console.log("got ), nest_level="+nest_level)
			nest_level--
			newly_added_tip = false
			going_down = true
			let in_squote = false
			// read past any trailing node label or branch length (already processed)
			for (index; index < end; index++) {
				let cur_char = newick.charAt(index+1)
				if (cur_char == "'") { //handle single quotes
					if (in_squote) 
						in_squote = false
					else
						in_squote = true						
				}
				if (!in_squote & [',', ')', ';'].indexOf(cur_char) >= 0) {
					//update index to just before the next significant symbol
					break
				}
			}
		}
		else if (tree_char == ',') {
			//console.log("got comma, nest_level="+nest_level)
			going_down = true
		}
		else if (tree_char == ';') {
			going_down = true
			//break; // end of newick data
		}
		else { // must be making of a new node -- either terminal or internal
			let is_tip = true
			let start_node_info_pos = index
			if (debug > 1)
				console.log('start new node (or origin) ')
			if (tree_char == '(') {
				is_tip = false
				let nest_level = 1
				for (start_node_info_pos = index+1; start_node_info_pos < end; start_node_info_pos++) {
					const cur_char = newick.charAt(start_node_info_pos)
					if (cur_char == '(') 
						nest_level++
					else if (cur_char == ')')
						nest_level--
					if (nest_level == 0) {
						start_node_info_pos++
						break
					}
				}
			}
			let in_squote = false
			for (var end_node_info_pos = start_node_info_pos; end_node_info_pos < end; end_node_info_pos++) {
				cur_char = newick.charAt(end_node_info_pos)
				if (cur_char == "'") { //handle single quotes
					if (in_squote) 
						in_squote = false
					else
						in_squote = true						
				}
				else if ( ! in_squote) 
				{
					if ([',', ')', ';'].indexOf(cur_char) >= 0) {
						break
					}
				}
			}
			let node_label = newick.substring(start_node_info_pos, end_node_info_pos)
			if (debug > 1)
				console.log("node info: "+node_label)
			let branch_length = 1.0
			let matchResult = node_label.match(/(.*):(\d+\.\d+)$/)
			if (matchResult) {
				branch_length = parseFloat(matchResult[2])
				node_label = matchResult[1]
				if (debug > 1)
					console.log('bl regex result: '+branch_length+", label="+node_label)
			}
			let support = 0.0
			node_label = node_label.replace(/^'|'$/g, '') // strip off quotes
			if (! is_tip) { // if not tip, label may be support value - if it is a number
				matchResult = node_label.match(/^([\d.]+)(.*)/)
				if (matchResult) {
					if (debug > 1)
						console.log('sup regex result: '+matchResult)
					support = parseFloat(matchResult[1])
					node_label = matchResult[2]
					node_label = node_label.replace(/^:/, '')
				}
			}
			let rank = ''
			matchResult = node_label.match(/(\w)__/)
			if (matchResult) {
				if (debug > 1)
					console.log('rank regex result: '+matchResult)
				rank = matchResult[1] // just grab first one (can be multiple, ordered?)
			}
			//debugger
			node_num++
			let node_id = node_label
			if (node_label.length == 0)
				node_id = "Node_"+node_num //create a unique id

			cur_node = create_node(node_id, parent_node = cur_node, node_label=node_label, branch_length=branch_length, node_support=support)
			if ((stop_rank != '') & (stop_rank == rank)) {
				if (debug)
					console.log("hit stop rank "+rank)
				is_tip = true
				cur_node.setAttribute("newick_start", index+1)	
				cur_node.setAttribute("newick_end", end_node_info_pos)	
			}
			if (is_tip) {
				set_node_ordinal(cur_node, num_tips)
				num_tips++
				index = end_node_info_pos - 1 // move index into newick string to end (skip interal taxa, possibly)
			}
			set_node_label_vis(cur_node, is_tip) // show taxon label for tips, tooltip otherwise
			nest_level++
		}
		if (going_down) {
			if (debug > 1)
				console.log("going down: cur_node = "+cur_node.getAttribute('id'))
			set_node_depth_from_children(cur_node)
			//debugger
			update_node_ordinal_from_children(cur_node)
			// go down to parent of current node
			cur_node = cur_node.parentNode
			//console.log("cur_node = "+cur_node.getAttribute('id'))
			going_down = false
		}
	}
	console.log('after parse: cur_node='+cur_node.id)
	//debugger
	return cur_node
}

embed_tree_x = function(target = null) {
	if (false & debug) {
		message = "embed_tree_x("
		if (target)
			message += ", "+target
		message += ")"
		console.log(message)
	}

	let node_elements = []
	if (target) 
		node_elements = target.querySelectorAll('.subtree')
	else
		node_elements = svgDocument.querySelectorAll('.subtree')
	for (const node of node_elements) {
		embed_node_x(node)
	}
}

embed_tree_y = function(target = null) {
	if (debug) {
		message = "embed_tree_y("
		if (target)
			message += ", "+target
		message += ")"
		console.log(message)
	}

	node_elements = []
	if (target) 
		node_elements = target.querySelectorAll('.subtree')
	else
		node_elements = svgDocument.querySelectorAll('.subtree')
	for (const node of node_elements) {
		embed_node_y(node)
	}
}
traverse_subtree = function(target) { // node on tree(g element)
	console.log("traverse_subtree( "+target.id+")");
	let visited = {};
	let done = {};
	let node = target;
	let target_id = target.getAttribute('id')
	let i = 0
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
			if (debug)
				console.log(comment)
		}
		let next_node = null;
		for (const child of node.children) {
			if (child.tagName == 'text' & debug > 1) { // assume only tip nodes have a text child
				console.log(" text child="+child.id+",  visited="+ visited[child.id]+", y="+child.getAttribute('y'))
			}
			else if (child.tagName == 'g') {
				if (! visited[child.id]) {
					next_node = child;
					if (debug > 1)
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
			if (debug > 2)
				console.log("going down to "+next_node.id+", done="+done[target_id])
		}
		node = next_node;
	}
	
	console.log("done traversing subtree")
}

set_tip_order = function(target, min_ord = 0) { 
	console.log("set_tip_order( "+target.id+", "+min_ord+")");
	let visited = {};
	let done = {};
	let node = target;
	let cur_ordinal = min_ord;
	while (! done[target.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			visited[node.id] = true
			if (debug > 1)
				console.log("visiting "+node.id)
			if (node.matches(".tip") & node.tagName == 'g') {
				//console.log(" tip child="+node.id+",  curord="+ cur_ordinal)
				set_node_ordinal(node, cur_ordinal)
				cur_ordinal++
			}
		}
		let next_node = null;
		for (const child of node.children) {
			if (child.tagName == 'g') {
				if (! visited[child.id]) {
					next_node = child;
					if (debug > 1)
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
			if (debug > 1)
				console.log("going down to "+next_node.id+", done="+done[target.id])
		}
		node = next_node;
	}
	console.log("set_tip_order done");
}

swap_descendants = function(target) { // assumes bifurcating tree (two subtrees per node)
	let firstChild = null
	let lastChild 
	if (debug > 1)
		console.log('swap_descendants: '+target.id)
	for (child of target.children) {
		if (child.tagName == 'g') {
			if (debug > 1)
				console.log('child: '+child.id+", "+child.getAttribute('ordinal'))
			if (firstChild)
				lastChild = child
			else
				firstChild = child
		}
	}
	// swap order of nodes, put last node first
	if (debug > 1)
		console.log("swap children: "+lastChild.getAttribute('id')+", "+firstChild.getAttribute('id'))
	target.insertBefore(lastChild, firstChild);
	if (debug > 1)
		for (child of target.children) 
			if (child.tagName == 'g') 
				console.log('child: '+child.id+", "+child.getAttribute('ordinal'))
}

orderTree=function(larger_subtrees_up=false) {
	console.log("orderTree() larger_subtrees_up = " + larger_subtrees_up);
	let num_descendants = {};
	let visited = {};
	let done = {};
	let root = get_root();
	let node = root;
	// traverse subtree
	while (! done[root.id]) {
		if (! visited[node.id]) {
			// pre-order operations
			// console.log("visit node "+node.id);
			visited[node.id] = true
			num_descendants[node.id] = 0;
		}
		let next_node = null;
		let sum_of_child_descendants = 0;
		for (const child of node.children) {
			//console.log(" child="+child.id+", tagName="+child.tagName+", visited="+visited[child.id])
			if (child.tagName == 'g') {
				if (visited[child.id]) {
					sum_of_child_descendants += num_descendants[child.id];
				}
				else {
					next_node = child;
					break;
				}
			}
			else if (child.tagName == 'text') {
				sum_of_child_descendants = 1;
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
	let all_nodes = document.querySelectorAll(".subtree");
	let any_changed = false;
	for (let node of all_nodes) {
		let child_num_descendants = [];
		for (let child of node.children) 
			if (child.matches('.subtree'))
				child_num_descendants.push(num_descendants[child.id]);
		if (child_num_descendants[0] < child_num_descendants[1]) {
			swap_descendants(node);
			any_changed = true;
		}
	}
	if (any_changed) {
		set_tip_order(get_root(), 0)
		embed_tree_y()
		embed_tree_x()
	}
	return;
}

update_node_ordinal_from_children = function(target) {// assume tip nodes have had ordinal pos set, update (fractional) ordinal pos of interior nodes
	if (target.matches('.tip')) {
		if (debug > 1)
			console.log("up..ord: terminal node, ordinal="+target.getAttribute('ordinal'))
		return(0)
	}
	let new_ord = 0;
	let num_children = 0;
	for (const child of target.children) {
		if (child.tagName == 'g') {
			let child_ord = parseFloat(child.getAttribute('ordinal'))
			new_ord += child_ord;
			num_children++;
			if (debug > 1)
				console.log(" got child_node ordinal of "+child_ord);
		}
	}
	if (! num_children) {
		console.log("No child nodes found, returning")
		return(0)
	}
	new_ord /= num_children;
	if (debug > 1)
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
		console.log("order="+target.getAttribute('ordinal'))
		console.log("p: "+target.parentNode.getAttribute('id'))
		if (target.matches(".tip")) 
			target.classList.toggle('highlight');
		else {
			//console.log("target="+target.id+", h="+target.matches(".highlight"))
			let turn_on = true //target.matches('.highlight');
			let descendant_tips = target.querySelectorAll('.tip', 'g');
			num_on = 0
			for (const node of descendant_tips) 
				if (node.matches('.highlight'))
					num_on++
			if (num_on == descendant_tips.length)
				turn_on = false
			console.log("turn-on="+turn_on+", tips="+descendant_tips.length)
			for (const node of descendant_tips) {
			   console.log("des tip="+node.id)
			   if (turn_on) 
				{node.classList.add('highlight');}
			   else 
				{node.classList.remove('highlight');}
			}
		}
	}
	else if (action == 'nodeinfo') {show_node_info(target);}
	else if (action == 'reroot') {root_below_node(target);}
	else if (action == 'order_tree') {orderTree();}
	else if (action == 'newick') {generate_newick(target);}
	else if (action == 'expand_taxon') {
		if (node.hasAttribute('newick_start')) 
			expand_node(node)
			
	}
	else if (action == 'swap') {
		const min_ord = get_node_min_ord(target)
		console.log("try swapping nodes: "+target.id+", minOrd="+min_ord+", num_tips="+num_tips);
		swap_descendants(target);
		set_tip_order(target, min_ord)
		embed_tree_y(target=target)
		embed_tree_x()
		for (child of target.children) 
			if (child.tagName == 'g') 
				console.log('xild: '+child.id+", "+child.getAttribute('ordinal'))
	}
}

global_action=function() {
	let select = document.getElementById("global_action_select");
	let action = select.value;
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
	else if (action == 'generate_json_newick') {
		generate_json_newick();
	}
	else if (action == 'list_highlighted') {
		highlighted_tips = svgDocument.querySelectorAll(".highlight");
		for (tip of highlighted_tips)
			console.log(tip.id)
	}
	else if (action == 'save_svg') {
		svg_txt = svgDocument.outerHTML
		console.log("save svg: \n"+svg_txt.substring(0,88))
	}
}

get_node_min_ord = function(node) {
	let tip_elements = node.querySelectorAll('.tip')
	let min_ord = num_tips
	for (tip of tip_elements) {
		const ord = tip.getAttribute('ordinal')
		if (ord != null & ord < min_ord) {
			min_ord = ord
			//console.log("tip: "+tip.getAttribute('label')+", min_ord now "+min_ord)
		}
	}
	if (debug)
		console.log("get_node_min_ord("+node.getAttribute('label')+", returning="+min_ord)
	return(min_ord)
}

highlight_taxon = function(target_taxon_id) {
   console.log('highglight_taxon('+target_taxon_id)
   h_elements = document.querySelectorAll('.highlight')
   for (h of h_elements)
	h.classList.remove('highlight')
   tip_elements = document.querySelectorAll('.tip');
   let tips_in_taxon = [];
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


initialize_annotation = function(initial_label= null)
{
	if (debug)
		console.log("initialize_annotation");
	let select = document.getElementById("annotation_field_select");
	if (select) {
	    let option = document.createElement('option');
	    option.text = option.value = 'id';
	    select.add(option, 0);
	    option = document.createElement('option');
	    option.text = option.value = 'label';
	    select.add(option, 0);
	    let i=0
	    for(const field of annotation) {
		    if (debug & i < 6) {
			    console.log("annotation field "+field);
			    i++;
		    }
		option = document.createElement('option');
		option.text = option.value = field;
		select.add(option, 0);
	    }
	    select.onchange=function(){relabel_tips(this.value)};
	    if (initial_label & annotation[initial_label])  {
		    if (debug) {
			    console.log('starting_label = '+initial_label)
		    }
		    select.value=initial_label;
		    relabel_tips(initial_label);
	    }
	}
}

