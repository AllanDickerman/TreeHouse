# web server for BVBRC trees
# mapping accessory genome onto a core-genome tree
import sys
import re
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from urllib.parse import parse_qs
import json
import os.path
import glob
import json

#bvbrc_name_lineage_file = "/Users/allan/git/TreeHouse/gtdb/bvbrc_genomes_in_gtdb_tree_with_lineage.txt"
ncbi_parent_rank_name_file = "/Users/allan/git/TreeHouse/web_server/selected_ncbi_taxon_parent_rank_name.txt"
#gtdb_taxonomy_file = "/Users/allan/git/TreeHouse/gtdb/bvbrc_gtbd_reference_taxonomy.txt"
#tree_data = '.' #'../gtdb'
hostName = "localhost"
serverPort = 8080
#bvbrcTaxonTrees = None
#tree_data = sys.argv[1]
#state_mapped_tree = {}

class TreeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        parsed = urlparse(self.path)
        path = parsed.path.lstrip('/')
        print("Parsed query = "+parsed.query)
        print("stripped path = "+path)
        if os.path.isfile(path):
            self.send_header("Content-type", "text/html")
            self.end_headers()
            print("found file "+path)
            with open(path) as file_to_serve:
                self.wfile.write(bytes(file_to_serve.read(), "utf-8"))
            return
        elif path == 'pangenome':
            self.send_header("Content-type", "text/html")
            self.end_headers()
            data_name = parsed.query
            pangenome = PangenomeData(data_name)
            state_mapped_tree[data_name] = pangenome
            print("state_mapped_trees we have: {}".format(state_mapped_tree.keys()))
            print("{} in state_mapped_tree = {}".format(data_name, data_name in state_mapped_tree))
            response_html = pangenome.get_html()
            self.wfile.write(bytes(response_html, "utf-8"))
            return
        elif path == 'get_pangenome_data':
            query_dict = parse_qs(parsed.query)
            print("query_dict = {}".format(query_dict))
            response_json = None
            if 'tree' in query_dict:
                tree_name = query_dict['tree'][0]
                print("tree_name = {}, character_name = {}".format(tree_name, character_name))
                print("state_mapped_trees we have: {}".format(state_mapped_tree.keys()))
                print("{} in state_mapped_tree = {}".format(tree_name, tree_name in state_mapped_tree))
                if tree_name in state_mapped_tree:
                    pangenome = state_mapped_tree[tree_name]
                if 'character' in query_dict:
                    character_name = query_dict['character'][0]
                    print("character_name = {}".format(character_name))
                    print("attempt getCharacterStatesJson")
                    response_json = pangenome.getCharacterStatesJson(character_name)
                elif 'gene_umap' in query_dict:
                    print("attempt getGeneUmapCoords")
                    response_json = pangenome.getGeneUmapCoords()
            if response_json:
                #print("retval={}".format(response_json))
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(response_json.encode("utf-8"))
                return

        # if we get here we failed to interpret request
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><head><title>Uninterpretable Request</title></head>", "utf-8"))
        self.wfile.write(bytes("<body>", "utf-8"))
        self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
        self.wfile.write(bytes("<p>path: %s</p>" % path, "utf-8"))
        self.wfile.write(bytes("<p>query: %s</p>" % parsed.query, "utf-8"))
        self.wfile.write(bytes("</body></html>", "utf-8"))
        return

class PangenomeData:
    def __init__(self, data_name):
        self.name = data_name
        if not os.path.exists(data_name):
            print("tried to find pangenome data for {}, not found".format(data_name))
            return
        # read tree
        if os.path.exists(os.path.join(data_name, "RAxML_nodeLabelledRootedTree."+data_name)):
            with open(os.path.join(data_name, "RAxML_nodeLabelledRootedTree."+data_name)) as F:
                self.newick = F.read().strip()
        # modify tree so node identifiers don't look like bootstrap support numbers
        self.newick = re.sub(r"\)(\d+)(?=[(),])", r")Node_\1", self.newick)
        print("modified tree = \n"+self.newick)

        self.node_states = {}
        # read data for ancestral nodes
        if os.path.exists(os.path.join(data_name, "RAxML_marginalAncestralStates."+data_name)):
            print("try reading anc states {}".format(os.path.join(data_name, "RAxML_marginalAncestralStates."+data_name)))
            with open(os.path.join(data_name, "RAxML_marginalAncestralStates."+data_name)) as F:
                for line in F:
                    (node, states) = line.strip().split()
                    # modify interior node labels that look like support values -- to match manipulation on tree
                    node = re.sub(r"\A(\d)", r"Node_\1", node)
                    self.node_states[node] = states
        # look for then read file with ancestral states (internal nodes on tree)
        list_files = glob.glob(os.path.join(data_name, "*chars.phy"))
        if len(list_files) == 1:
            print("try reading taxon states {}".format(list_files[0]))
            with open(list_files[0]) as F:
                line = F.readline()
                num_taxa, num_chars = line.strip().split() 
                for line in F:
                    taxon, states = line.strip().split()
                    self.node_states[taxon] = states
        print("Tip and node ids for states:\n"+" ".join(self.node_states.keys()))

        # look for file with gene umap coords
        self.genes_umap_cords_file = None
        list_files = glob.glob(os.path.join(data_name, "*chars_umap.json"))
        if len(list_files) == 1:
            self.genes_umap_cords_file = list_files[0]

        # read ordered list of character names, so we can match names to columns of matrix
        list_files = glob.glob(os.path.join(data_name, "*chars.list"))
        if len(list_files) == 1:
            print("try reading character names {}".format(list_files[0]))
            with open(list_files[0]) as F:
                self.character_names = []
                for i, line in enumerate(F):
                    index, name = line.strip().split("\t")
                    self.character_names.append(name)

    def getCharacterStatesJson(self, character_name):
        print("getCharacterStatesJson({})".format(character_name))
        index = -1
        retval = {}
        try:
            index = self.character_names.index(character_name)
            print("found {} in character_names at index {}".format(character_name, index))
            for node in self.node_states:
                retval[node] = self.node_states[node][index]
        except ValueError as ve:
            print("exception {}".format(ve))
        return json.dumps(retval, indent=2)

    def getGeneUmapCoords(self, character_name):
        print("getGeneUmapCoords()")
        if self.genes_umap_cords_file:
            with open(self.genes_umap_cords_file) as F:
                retval = F.read()
                return json.dumps(retval, indent=2)
        return None

    def get_html(self):
        failure_message = []
        if not self.newick:
            failure_message.append("No tree found for {}".format(self.name))
        if not self.node_states:
            failure_message.append("No node states found for {}".format(self.name))
        if not self.character_names:
            failure_message.append("No character names found for {}".format(self.name))
        if len(failure_message):
            retval = "<html>\n"
            retval += "<h3>Problem retrieving data for {}</h3>\n".format(self.name)
            for line in failure_message:
                retval += "<p>"+line+"</p>\n"
            retval += "</html>"
            return retval
            
        print("newick = "+self.newick)
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "</head><body>\n"
        retval += "<p><a href='/'>Home</a></p>\n"
        retval += "<h3>Tree with Pangenome: {}</h3>\n".format(self.name)

        retval += "<table>"
        retval += "<td><label for='annotation_field_select'>Character:</label><br>\n"
        retval += "<select id='annotation_field_select'>\n"
        retval += "</select>\n"
        retval += "&nbsp;</td>";

        retval += "<td>\n";
        retval += "<label for='node_action_select'>Node Action</label><br>\n"
        retval += "<select id='node_action_select'>\n"
        retval += "<option value='highlight'>Highlight Nodes</option>\n"
        retval += "<option value='nodeinfo'>Node Info</option>\n"
        retval += "<option value='swap'>Swap Children</option>\n"
        retval += "<option value='newick'>Newick Subtree</option>\n"
        retval += "</select>\n"
        retval += "&nbsp;";
        retval += "</td><td>\n";
        retval += "<label for='global_action_select'>Global Action</label><br>\n"
        retval += "<select id='global_action_select' onchange='global_action()'>\n";
        retval += "<option value='generate_newick'>Generate Newick</option>\n"
        #retval += "<option value='save_arrangement'>Save Arrangement</option>\n"
        retval += "<option value='list_highlighted'>List Highlighted</option>\n"
        #retval += "<option value='generate_json_newick'>Generate Json Newick</option>\n"
        retval += "<option value='order_tree_up'>Order Tree Up</option>\n"
        retval += "<option value='order_tree_down'>Order Tree Down</option>\n"
        retval += "<option value='save_svg'>Save as SVG</option>\n"
        retval += "</select>\n"
        retval += "</td></tr></table>"

        retval += "<div id='svg_container' style='width: 800px; height: 600px; overflow-y: scroll;'>\n"
        retval += "</div>"
        if self.gene_umap_coords_file:
            retval += "Genes UMAP Plot\n"
            retval += "<div id='genes_umap_container' style='width: 800px; height: 600px; overflow-y: scroll;'>\n"
            retval += "</div>\n"
            retval += "<script type='text/javascript' src='scatterplot.js'></script>\n";
            retval += "<script type='text/javascript'>\n";
            retval += "debug = true;\n" 
            retval += "\ncreate_plot(container='genes_umap_container', data_name={})\n".format(self.name)
            retval += "</script>\n";



        #genome_taxon = {}
        genome_ids = re.findall("[(,]([^(),:]+)", self.newick)
        annotation = {}
        #annotation['species'] = {}
        #annotation['bvbrc_name'] = self.genome_name
        #tip_label = {'label': species}
        #self.addNcbiTaxonAnnotation(genome_ids, annotation)
       # self.addGtdbTaxonAnnotation(genome_ids, annotation)

        retval += "<script type='text/javascript' src='bvbrc_tree.js'></script>\n";
        retval += "<script type='text/javascript'>\n";
        retval += "debug = true;\n" 
        retval += "tree_id = \"{}\";\n".format(self.name)
        retval += "const newick_tree_string = \""+self.newick+"\";\n" 
        #retval += "tree_annotation = "+json.dumps(annotation, indent=4)+";\n"  
        retval += "annotation_labels = "+json.dumps(self.character_names, indent=4)+";\n"  

        retval += "\ncreate_tree(newick_tree_string, annotation_labels=annotation_labels)\n"
        #retval += "initialize_annotation()\n";
        retval += "</script>\n";
            
        retval += "</body></html>"
        return retval
        

class BvbrcTaxonTrees:
    def __init__(self, lineage_file, ncbi_taxonomy_file, gtdb_taxonomy_file, trees_file):
        self.trees = {}
        self.genome_lineage = {}
        self.taxon_name = {}
        self.taxon_parent = {}
        self.tree_parent = {}
        self.tree_children = {}
        self.tree_taxon = {}
        self.taxon_tree = {}
        self.tree_size = {}
        self.read_bvbrc_lineage(lineage_file)
        self.read_ncbi_taxonomy(ncbi_taxonomy_file)
        self.read_gtdb_taxonomy(gtdb_taxonomy_file)
        if os.path.isfile(trees_file): # a file of names of tree files
            with open(trees_file) as F:
                tree_files = F.read().split("\n")
                print("number of tree files: {}".format(len(tree_files)))
                for file in tree_files:
                    tree_name = os.path.basename(file)
                    m = re.match('(\S+)_(order|family|genus)_.*', tree_name)
                    if m:
                        taxon = m.group(1)
                        rank = m.group(2)
                        with open(file) as F:
                            tree_text = F.read().rstrip()
                        self.register_tree(tree_name, tree_text, taxon, rank)
                        print("got tree for {}, len {}, ex: {}\n".format(tree_name, len(tree_text), tree_text[0:20]))
                    else:
                        print("could not parse taxon or rank from {}".format(tree_name))
        return

    def read_bvbrc_lineage(self, file_name):
        self.genome_name = {}
        self.genome_taxon = {}
        self.taxon_parent = {}
        self.taxon_name = {}
        with open(file_name) as F:
            for line in F:
                bvbrc_id, genome_name, id_lineage, name_lineage = line.rstrip().split("\t")
                taxon_names = name_lineage.split('::')
                taxon_ids = id_lineage.split('::')
                self.genome_name[bvbrc_id] = genome_name
                self.genome_taxon[bvbrc_id] = taxon_ids[-1]
                #self.gtdb_species[gtdb_id] = species
                for i in range(len(taxon_ids)-1):
                    self.taxon_parent[taxon_ids[i+1]] = taxon_ids[i]

    def read_ncbi_taxonomy(self, file_name):
        self.taxon_parent = {} # over-write this
        self.taxon_rank = {} 
        self.name_taxonid = {}
        with open(file_name) as F:
            for line in F:
                taxon_id, parent_id, rank, name = line.rstrip().split("\t")
                self.taxon_parent[taxon_id] = parent_id
                self.taxon_name[taxon_id] = name
                self.taxon_rank[taxon_id] = rank
                self.name_taxonid[name] = taxon_id
    
    def read_gtdb_taxonomy(self, file_name):
        self.gtdb_taxon_parent = {} # over-write this
        self.gtdb_taxon_rank = {} 
        self.bvbrc_gtdb = {}
        abbrev_rank = {"s":'species', 'g':'genus', 'f':'family', 'o':'order', 'c':'class', 'p':'phylum', 'd':'division'}
        with open(file_name) as F:
            for line in F:
                bvbrc_id, gtdb_id, gtdb_lineage = line.rstrip().split("\t")
                self.bvbrc_gtdb[bvbrc_id] = gtdb_id
                taxa = gtdb_lineage.split(";")
                taxa.reverse() # so we go from species (lowest) to division (highest)
                if len(self.gtdb_taxon_parent) < 8:
                    print("gtdb lineage: {}".format(taxa))
                taxon = gtdb_id
                self.gtdb_taxon_rank[gtdb_id] = 'gtdb_id'
                for parent in taxa:
                    rank = 'gtdb_id'
                    name = parent
                    if '__' in parent:
                        (rank, name) = parent.split('__')
                        if rank in abbrev_rank:
                            rank = abbrev_rank[rank]
                    self.gtdb_taxon_parent[taxon] = name
                    self.gtdb_taxon_rank[name] = rank
                    taxon = name
                self.gtdb_taxon_parent[taxon] = None
    
    def register_tree(self, tree_name, newick, taxon, rank):
        self.trees[tree_name] = newick
        self.tree_taxon[tree_name] = taxon
        self.taxon_tree[taxon] = tree_name
        self.taxon_rank[taxon] = rank

        genome_ids = re.findall("[(,](\d+\.\d+):", newick)
        # should we store links of all thes to the trees they belong to??
        self.tree_size[tree_name] = len(genome_ids)

    def get_tree_list_html(self):
        print("get_taxon_list()")
        #for taxon in self.tree_taxon:
            #print(tree_taxon[taxon])
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "</head><body>\n"
        retval += "<h3>BVBRC Taxon Trees</h3>\n"
        for taxon in sorted(self.taxon_tree):
            rank = self.taxon_rank[taxon]
            retval += "<a href='taxon?{}'>{} {}<br>\n".format(taxon, rank, taxon)

        if (False):
            retval += "<table>"
            retval += "<tr><th>Tree</th><th>Taxon</th><th>Tips</th><th>Genera</th><th>Families</th></tr>\n";
            for tree in sorted(self.trees):
                for taxon in sorted(self.tree_taxon[tree]):
                    record = self.tree_taxon[tree][taxon]
                    retval += "<tr><td onclick=\"window.location.href='tree?{}'\">{}</td><td onclick=\"window.location.href='tree?{}&taxon={}'\">{}</td><td>{}</td><td> onclick=\"window.location.href='tree?{}&taxon={}&stop_at=genus'\">{}</td><td onclick=\"window.location.href='tree?{}&taxon={}&stop_at=family'\">{}</td></tr>\n".format(tree, tree, tree, taxon, taxon, record['num_tips'], tree, taxon, record['num_genera'], tree, taxon, record['num_families'])
            retval += "</table>\n"
        retval += "</html>\n"
        return retval

    def get_tree_html(self, taxon):
        print("tree_data.show_gtdb_taxon_tree({})".format(taxon))

        if taxon in self.taxon_tree:
            tree_name = self.taxon_tree[taxon]
            newick = self.trees[tree_name]
        else:
            return "<html>No taxon named {} found.</html>".format(taxon)
            
        print("newick = "+newick)
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "</head><body>\n"
        retval += "<p><a href='/'>Home</a></p>\n"
        retval += "<h3>Tree {} {}</h3>\n".format(tree_name, taxon)

        retval += "<table>"
        if (1):
            retval += "<td><label for='annotation_field_select'>Label:</label><br>\n"
            retval += "<select id='annotation_field_select'>\n"
            retval += "</select>\n"
            retval += "&nbsp;</td>";
        retval += "<td>\n";
        retval += "<label for='node_action_select'>Node Action</label><br>\n"
        retval += "<select id='node_action_select'>\n"
        retval += "<option value='highlight'>Highlight Nodes</option>\n"
        retval += "<option value='nodeinfo'>Node Info</option>\n"
        retval += "<option value='swap'>Swap Children</option>\n"
        retval += "<option value='expand'>Expand Taxon</option>\n"
        retval += "<option value='newick'>Newick Subtree</option>\n"
        retval += "</select>\n"
        retval += "&nbsp;";
        retval += "</td><td>\n";
        retval += "<label for='global_action_select'>Global Action</label><br>\n"
        retval += "<select id='global_action_select' onchange='global_action()'>\n";
        retval += "<option value='generate_newick'>Generate Newick</option>\n"
        #retval += "<option value='save_arrangement'>Save Arrangement</option>\n"
        retval += "<option value='list_highlighted'>List Highlighted</option>\n"
        #retval += "<option value='generate_json_newick'>Generate Json Newick</option>\n"
        retval += "<option value='order_tree_up'>Order Tree Up</option>\n"
        retval += "<option value='order_tree_down'>Order Tree Down</option>\n"
        retval += "<option value='save_svg'>Save as SVG</option>\n"
        retval += "</select>\n"
        retval += "</td></tr></table>"

        retval += "<div id='svg_container' style='width: 800px; height: 600px; overflow-y: scroll;'>\n"
        retval += "</div>"

        #genome_taxon = {}
        genome_ids = re.findall("[(,]([^(),:]+)", newick)
        annotation = {}
        #annotation['species'] = {}
        #annotation['bvbrc_name'] = self.genome_name
        #tip_label = {'label': species}
        self.addNcbiTaxonAnnotation(genome_ids, annotation)
        self.addGtdbTaxonAnnotation(genome_ids, annotation)

        retval += "<script type='text/javascript' src='bvbrc_tree.js'></script>\n";
        retval += "<script type='text/javascript'>\n";
        retval += "const newick_tree_string = \""+newick+"\";\n" 
        retval += "debug = true;\n" 
        retval += "tree_annotation = "+json.dumps(annotation, indent=4)+";\n"  

        retval += "\ncreate_tree(newick_tree_string, input_annotation=tree_annotation, initial_label='bvbrc_name')\n"
        retval += "\n</script>\n";
            
        retval += "</body></html>"
        return retval

    def addNcbiTaxonAnnotation(self, genome_ids, annotation):
        for bvbrc_id in genome_ids:
            taxon_id = self.genome_taxon[bvbrc_id]
            prev_taxon = None
            while (taxon_id and taxon_id != prev_taxon):
                rank = 'ncbi_' + self.taxon_rank[taxon_id]
                if rank not in annotation:
                    annotation[rank] = {}
                annotation[rank][bvbrc_id] = self.taxon_name[taxon_id]
                prev_taxon = taxon_id
                taxon_id = self.taxon_parent[taxon_id]
        return annotation

    def addGtdbTaxonAnnotation(self, genome_ids, annotation):
        for bvbrc_id in genome_ids:
            gtdb_taxon = self.bvbrc_gtdb[bvbrc_id]
            prev_taxon = None
            while (gtdb_taxon and gtdb_taxon != prev_taxon):
                rank = 'gtdb_' + self.gtdb_taxon_rank[gtdb_taxon]
                if rank not in annotation:
                    annotation[rank] = {}
                annotation[rank][bvbrc_id] = gtdb_taxon
                prev_taxon = gtdb_taxon
                gtdb_taxon = self.gtdb_taxon_parent[gtdb_taxon]
        return annotation

            

if __name__ == "__main__":        
    webServer = HTTPServer((hostName, serverPort), TreeHandler)
    print("Server started http://%s:%s" % (hostName, serverPort))
    #file_of_tree_files = sys.argv[1]

    #bvbrcTaxonTrees = BvbrcTaxonTrees(bvbrc_name_lineage_file, ncbi_parent_rank_name_file, gtdb_taxonomy_file, file_of_tree_files)
    #print("Files available:")
    #files = os.listdir()
    #for f in files:
    #    if (os.path.isfile(f)):
    #        print("file: {}".format(f))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        webServer.server_close()
        print("Server stopped.")

