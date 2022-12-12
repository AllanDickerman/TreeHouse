console.log("reading two_plot.js");

var annotation = {};
var treeSvgObject;
var plotSvgObject;
window.onload = function () {
	console.log("onload");
	treeSvgObject = document.getElementById('tree_svg').contentDocument;
	console.log("treeSvgObject = "+treeSvgObject);
	plotSvgObject = document.getElementById('scatter_svg').contentDocument;
	console.log("plotSvgObject = "+plotSvgObject);
	console.log("onload done");
};

tree_node_clicked=function(target) {
	//var action = document.getElementById("node_click_action_select").value;
	console.log("two_plot node_clicked target="+target.id+", plotSvg.defaultView = "+plotSvgObject.defaultView);
	//var plot_point = plotSvgObject.getElementById(target.id);
	//plot_point.toggleAttribute('highlight');
	//if (plotSvgObject.defaultViw.point_clicked) 
	//	plotSvgObject.defaultView.point_clicked(target.id);
	console.log("plotSvgObject = "+plotSvgObject);
	highlighted_nodes = get_highlighted_tree_ids();
	console.log("hilighted tree ids: "+highlighted_nodes.length)
	var plotDots = plotSvgObject.querySelectorAll('circle');
	console.log("plotDots to unhilight (all): "+plotDots.length)
	for (plotDot of plotDots) {
		plotDot.classList.remove('highlight');
	}
	for (gid of highlighted_nodes) {
		var plotPoint = plotSvgObject.getElementById(gid);
		console.log("highlight plot point: "+gid+", elem="+plotPoint.tagName)
		plotPoint.classList.add('highlight');
	}
}
get_highlighted_tree_ids = function() {
	console.log("get highligted tip ids");
	var selected_tip_id_list = [];
	tip_elements = treeSvgObject.querySelectorAll('.tip_name');
	for (const tip of tip_elements) {
		if (tip.matches('.highlight')) { selected_tip_id_list.push(tip.id); }
	}
	return(selected_tip_id_list);
}

console.log("done reading two_plot.js");

