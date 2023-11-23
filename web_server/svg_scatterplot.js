const ns = "http://www.w3.org/2000/svg" // store namespace

function* enumerate(iterable) {
	let i = 0;
	for (const x of iterable) {
		yield([i, x]);
		i++;
	}
}

class ScatterPlot {
	dataSource; // name of data collection when communicating with server
	dataSlot;   // there may be more than one plot associated with the data source
	container;  // html entity (a div) within which visualization happens
	svg;        // the svg document
	height=600;
	width = 800;

	constructor(container_id, source_name, data_slot) {
		this.container = document.getElementById(container_id);
		this.dataSource = source_name;
		this.dataSlot = data_slot;
		console.log("new ScatterPlot: "+this.container+" "+this.dataSource+" "+this.dataSlot)
		this.svg = document.createElementNS(ns, "svg")
		this.container.appendChild(this.svg)
		this.svg.setAttribute("id", this.container+"_"+this.dataSource+"_"+this.dataSlot+"svg")
		this.points = {}

		// set width and height
		this.svg.setAttribute("width", this.width)
		this.svg.setAttribute("height", this.height)
		this.svg.setAttribute('style', 'background-color: white; border: 1px solid rgb(144, 144, 144); font-size: 12px;')
		//debugger
		//const stylesheet = new CSSStyleSheet();
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
		sheet.insertRule("dot{r: 5; fill: red; opacity: 1; cursor: pointer}", 0);
		sheet.insertRule("dot.taxon{fill: red}", 0);
		sheet.insertRule("dot.tip{fill: orange}", 0);

	}

	async fetchPointCoords() {
		const url = "getTreeData?tree="+this.dataSource+"&data="+self.dataSlot;
		if (debug)
			console.log("fetching "+this.dataSlot+" for tree "+self.dataSource+": "+url);
		const response = await fetch(url);
		data = await response.json();
		return data
	}
	
	plotSplitData(data) {
		//split data format from pandas to_json(orient='split')
		//data = this.fetchPointCoords();
		console.log('plotSplitData()')
		console.log('data = '+data)
		console.log('data index = '+data["index"])
		console.log('data data type = '+typeof(data["data"]))
		let minX = data["data"][0][0]
		let minY = data["data"][0][1]
		let maxX = minX
		let maxY = minY
		for (const coord of data['data']) {
			if (coord[0] < minX) minX = coord[0];
			if (coord[1] < minY) minY = coord[1];
			if (coord[0] > maxX) maxX = coord[0];
			if (coord[1] > maxY) maxY = coord[1];
		}
		const spanX = (maxX - minX)*1.05
		const spanY = (maxY - minY)*1.05
		const scaleX = this.width / spanX
		const scaleY = this.height / spanY

		for (const [i, name] of enumerate(data['index'])) {
			console.log(i+" "+name)
			const coords = data['data'][i]
			console.log("data["+i+"] = "+coords)
			const scaledX = (coords[0] - minX) * scaleX
			const scaledY = (coords[0] - minY) * scaleY
			const dot = document.createElementNS(ns, "circle")
			dot.setAttribute('cx', scaledX+20)
			dot.setAttribute('cy', scaledY+10)
			dot.setAttribute('r', 5)
			dot.setAttribute('fill', 'red')
			dot.setAttribute('z', '-1') 
			dot.setAttribute('name', name); 
			//dot.onclick=this.pointClicked
			dot.classList.add('dot');
			this.svg.appendChild(dot);
			this.points[name] = dot;
		}

	}

	pointClicked() {
		console.log("point clicked")
	}
}
