
class PhyloNode {
	svg;     //   // the svg document
	tree;
	newick_start;
	id;
	branch_length;
	support;
	ypos;
	depth;  // distance to farthest descendant tip
	group;  // an svg g element
	circle; // an svg circle element
	branch;   // an svg path element for the branch
	parent_node; // the parent PhyloNode
	children = [];

	constructor(params) {   //tree, node_id, parent_node, branch_length=0, node_support=0) { 
		let message = "new PhyloNode:\n"
		for (const key in params) {
			var getClassOf = Function.prototype.call.bind(Object.prototype.toString);
			const paramType = typeof(params[key]);
			if (paramType != 'object')
				//message += key + ": "+getClassOf(params[key]) + "\n";
			//else
				message += key + ": "+params[key]+"\n";
		}
		console.log(message)
		this.tree = params['tree'];
		this.id = params['node_id'];
		if (params['newick_start'])
			this.newick_start = params['newick_start'];
		this.branch_length = params['branch_length'];
		if (params['support'] != undefined)
			this.support = params['support'];
		this.ypos = 0;
		this.group = document.createElementNS(ns, "g")
		this.group.setAttribute("id", this.id)
		this.group.setAttribute("y", 0)
		this.group.classList.add('subtree');
		this.group.classList.add('tip');
		message = "create_node("+this.id
		if (params['parent_node']) {
			message += ", p:"+params['parent_node'].id
			this.parent_node = params['parent_node']
			this.parent_node.append_child(this)
		}
		if (debug > 0)
			console.log(message)

		const transform = this.tree.svg.createSVGTransform()
		this.group.transform.baseVal.initialize(transform);

		this.circle = document.createElementNS(ns, "circle")
		this.circle.setAttribute('cx', '0')
		this.circle.setAttribute('cy', '0')
		this.circle.setAttribute('id', this.id)
		//this.circle.setAttribute('z', '-1') 
		this.circle.onclick=function(e) {
			
			console.log("circle clicked for "+e.target.id)
			document.getElementById('node_click_message').innerHTML = "Node: "+this.id
		}

		this.circle.classList.add('clickCircle')
		this.group.appendChild(this.circle)

		this.branch = document.createElementNS(ns, "path")
		this.branch.classList.add('branch')
		this.group.appendChild(this.branch)
	}

	append_child(node) {
		this.children.push(node)
		this.group.appendChild(node.group)
		this.group.classList.remove('tip')
		node.parent_node = this;
	}

	set_branch_length(bl) {
		this.branch_length = bl;
		//node.transform.baseVal[0].matrix.e = bl
	}

	set_newick_start(start) { this.newick_start = start }

	set_depth_from_children = function() {
		let max_child_depth = 0;
		for (const child of this.children) {
			if (child.depth > max_child_depth)
				max_child_depth = child.depth;
		}
		const temp_depth = (this.branch_length + max_child_depth);
		this.depth = temp_depth;
		if (debug > 1) {
			console.log("set_depth_from_children("+this.id+")\nmax_child_depth="+max_child_depth+", depth="+this.depth)
		}
	}

	set_ordinal(ord) {
		//console.log('set_node_ordinal('+node.getAttribute('id')+", "+ord)
		this.ordinal = ord
	}

	set_support(value) {
		this.support = value;
	}

	add_label_slot() {
		// only need to do this once, then use sete_label to change text
		if (this.labelDisplay) return;
		this.labelDisplay = document.createElementNS(ns, 'text')
		this.labelDisplay.setAttribute('dx', '7')
		this.labelDisplay.setAttribute('dy', this.ypos + 3)
		this.labelDisplay.textContent = this.id;
		this.group.appendChild(this.labelDisplay);
		if (debug > 1)
			console.log("add label slot: "+this.id);
	}

	set_label(label) {
		if (!this.labelDisplay) 
			this.add_label_slot();
		this.labelDisplay.textContent = label;
	}

	add_data_slot() {
		if (this.dataDisplay) return;
		this.dataDisplay = document.createElementNS(ns, 'text')
		this.dataDisplay.setAttribute('dx', '0')
		this.dataDisplay.setAttribute('dy', this.ypos + 9)
	}

	set_data(display_text) {
		if (!this.dataDisplay) 
			this.add_data_slot();
		this.dataDisplay.textContent = display_text;
	}

	show_info = function() {
		console.log("show_node_info "+node.id)
		if (this.label)
			console.log('label = '+this.label)
		console.log('bl = '+this.bl)
		console.log('support = '+this.support)
	}

	embed_y = function() {
		//console.log("embed_node_y("+this.id+"), dy:"+this.tree.delta_y+", ord:"+this.ordinal)
		if (this.children.length) {
			//console.log("num children = "+this.children.length)
			let new_ord = 0;
			for (const child of this.children) {
				new_ord += child.ordinal
			}
			new_ord /= this.children.length;
			this.ordinal = new_ord;
			//console.log("updated ord: "+this.ordinal)
		}
		this.ypos = (this.ordinal + 1) * this.tree.delta_y;
		this.circle.setAttribute('cy', this.ypos)
		if (this.labelDisplay)
			this.labelDisplay.setAttribute('y', this.ypos);
	}

	embed_x = function() {
		if (debug > 2) {
			console.log("embed_x("+this.id+")")
		}
		const path_length = this.branch_length * this.tree.x_scale;
		
		this.group.transform.baseVal[0].matrix.e = path_length;
		let d = "M0,"+this.ypos+" h-"+path_length;
		if (this.parent_node) {
			d = d + " V"+this.parent_node.ypos;
		}
		this.branch.setAttribute('d', d);
		//console.log('  '+this.id+': bl='+this.branch_length+', path.d = '+d)
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


}

