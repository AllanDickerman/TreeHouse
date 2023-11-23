const ns = "http://www.w3.org/2000/svg" // store namespace

function* enumerate(iterable) {
	let i = 0;
	for (const x of iterable) {
		yield([i, x]);
		i++;
	}
}

class PhyloTree {
	newick;     // newick string describing tree structure
	dataSource; // name of data collection when communicating with server
	dataSlot;   // there may be more than one plot associated with the data source
	container;  // html entity (a div) within which visualization happens
	svg;        // the svg document
	height;
	width = 800;
	delta_y = 12;  // vertical separation between tips
	x_scale = 1400;  // factor to multiply branch lengths by to get x dimensions for plotting
	tree_width_prop = 0.75; // proportion of figure width taken up by distance to farthest tip
	root = null;           // root node of tree
	nodes = {};     // dictionary of all nodes
	tips = [];      // list of tip nodes
	internal_nodes = [] // ordered list of internal nodes
	annotation; // a genome data manager object
	stop_rank;  // for specific case of reading GTDB tree and not parsing smaller taxa 

	constructor(params) { 
		this.container = document.getElementById(params['container_id']);
		this.newick = params['newick_string'];

		console.log("new PhyloTree: "+this.container+" "+this.newick.substring(0,30))
		console.log("container dims: "+this.container.clientHeight+" "+this.container.clientWidth)
		console.log("container innerHtml: "+this.container.innerHTML)
		this.container.innerHTML = "";
		this.svg = document.createElementNS(ns, "svg")
		this.container.appendChild(this.svg)

		this.svg.setAttribute('style', 'background-color: white; border: 1px solid rgb(144, 144, 144); font-size: 12px; width: 400px; height: 300px;')
		const stylesheet = document.createElementNS(ns, 'style');
		this.svg.appendChild(stylesheet);
		let sheets = document.styleSheets;
		let sheet;
		for(var i=0, length=sheets.length; i<length; i++){
		   sheet=sheets.item(i);
		   if (sheet.ownerNode == stylesheet) i
			break;
		}
		sheet.insertRule(".highlight{fill:red;}", 0);
		sheet.insertRule("circle{r: 5; fill: pink; opacity: 1; cursor: pointer}", 0);
		sheet.insertRule("circle.taxon{fill: red}", 0);
		sheet.insertRule("circle.tip{fill: orange}", 0);
		sheet.insertRule(".branch {fill: blue}", 0);


		this.parse_newick();
		console.log("newick parsed, num tips = "+this.tips.length+", num nodes = "+this.nodes.length)
		//console.log("delta_y = " + delta_y)
		// set width and height
		this.width = this.container.clientWidth;
		if (params['delta_y']) {
			this.delta_y = params['delta_y'];
			this.height = this.delta_y * (this.tips.length + 2)
		}
		else {
			this.height = this.container.clientHeight;
			this.delta_y = this.height/(this.tips.length +2);
			console.log("dimensions from container: "+this.height+", "+this.width);
		}
		this.svg.style.width = this.width
		this.svg.style.height = this.height

		//debugger
		this.embed_tree()

		for (const node of this.tips) {
			console.log("set label of node "+node)
			node.set_label(node.id);
		}
	}

	label_tips(labels) {
		if (debug)
			console.log("function label_tips "+field);
		for (const node of nodes) {
			console.log("node: "+node)
			if (labels[node.id] != undefined) {
				nodes.set_label(labels[node_id]);
			}
		}
	}


	parse_newick(start=0, parent_node=null) {
		// read from global newick string
		//debugger
		console.log("parse_newick("+start)
		let num_tips = 0;
		let node_num = 1;
		let going_down = false;
		let cur_node ;
		let nest_level = 0;
		let prev_i = start - 1;
		const end = this.newick.length;
		for (let index = start; index < end; index++) {
			const tree_char = this.newick.charAt(index)
			if (index <= prev_i) {
				debugger
				throw("index is too low")
			}
			prev_i = index
			if (tree_char == ')') {
				//if (debug > 1) console.log("got ), nest_level="+nest_level)
				nest_level--
				going_down = true
				let in_squote = false
				// read past any trailing node label or branch length (already processed)
				for (index; index < end; index++) {
					let cur_char = this.newick.charAt(index+1)
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
						const cur_char = this.newick.charAt(start_node_info_pos)
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
					const cur_char = this.newick.charAt(end_node_info_pos)
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
				let node_id = this.newick.substring(start_node_info_pos, end_node_info_pos)
				if (debug > 1)
					console.log("node info: "+node_id)
				let branch_length = 0
				let matchResult = node_id.match(/(.*):(\d+\.\d+)$/)
				if (matchResult) {
					branch_length = parseFloat(matchResult[2])
					node_id = matchResult[1]
					if (debug > 1)
						console.log('bl regex result: '+branch_length+", label="+node_id)
				}
				let support = 0.0
				node_id = node_id.replace(/^'|'$/g, '') // strip off quotes
				if (! is_tip) { // if not tip, label may be support value - if it is a number
					matchResult = node_id.match(/^([\d.]+)(.*)/)
					if (matchResult) {
						if (debug > 1)
							console.log('sup regex result: '+matchResult)
						support = parseFloat(matchResult[1])
						node_id = matchResult[2]
						node_id = node_id.replace(/^:/, '')
					}
				}
				let rank = ''
				matchResult = node_id.match(/(\w)__/)
				if (matchResult) {
					if (debug > 1)
						console.log('rank regex result: '+matchResult)
					rank = matchResult[1] // just grab first one (can be multiple, ordered?)
				}
				//debugger
				if (!this.root) node_id = 'root';
				if (node_id.length == 0)
					node_id = "Node_"+node_num; //create a unique id

				const node_params = {tree:this, node_id: node_id, parent_node: cur_node, branch_length: branch_length, support: support};
				const new_node = new PhyloNode(node_params);
				if (!this.root) {
					this.root = new_node;
					this.svg.appendChild(new_node.group)
				}
				this.nodes[node_id] = new_node
				cur_node = new_node

				if ((this.stop_rank != '') & (this.stop_rank == rank)) {
					if (debug)
						console.log("hit stop rank "+rank)
					is_tip = true
					cur_node.set_newick_start(index+1)
				}
				if (is_tip) {
					cur_node.set_ordinal(num_tips)
					num_tips++
					index = end_node_info_pos - 1 // move index into newick string to end (skip interal taxa, possibly)
					this.tips.push(cur_node)
				}
				else {
					this.internal_nodes.push(cur_node); //maintain ordered list of internal nodes
					node_num++;
				}
				nest_level++
			}
			if (going_down) {
				if (1 | (debug > 1))
					console.log("going down: '"+tree_char+"', cur_node = "+cur_node.id)
				//cur_node.update_ordinal_from_children()
				//debugger
				// go down to parent of current node
				console.log("go down to = "+cur_node.parent_node)
				cur_node = cur_node.parent_node
				going_down = false
			}
		}
		console.log('after parse: num nodes='+this.nodes.length)
	}

	embed_tree() {
		let message = "embed_tree()"
		console.log(message)
		for (const node of this.tips) {
			node.embed_y()
			console.log("node y = "+node.ypos)
		}
		for (const node of this.internal_nodes.reverse()) {
			node.embed_y()
			node.set_depth_from_children()
		}
		this.embed_tree_x()
	}

	embed_tree_x() {
		console.log('embed_tree_x: root.depth='+this.root.depth)
		this.x_scale = this.width/(this.root.depth / this.tree_width_prop) // should fill left half with branches, right side for names
		console.log('x_scale = '+this.x_scale)
		for (const node_id in this.nodes) {
			this.nodes[node_id].embed_x()
		}
	}

	update_tree_width_prop(value) {
		console.log("update_tree_width_prop: "+value);
		if ((value > 1) | (value < 0)) {
			console.log("value out of range: "+value);
			return;
		}
		this.tree_width_prop = value;
		this.embed_tree_x();
	}

}
