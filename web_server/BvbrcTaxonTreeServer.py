# web server for BVBRC taxon trees
import sys
import re
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
#import sqlite3
#import subprocess
import os.path
#import tempfile
import glob

bvbrc_name_lineage_file = "/Users/allan/git/TreeHouse/gtdb/bvbrc_genomes_in_gtdb_tree_with_lineage.txt"
ncbi_parent_rank_name_file = "/Users/allan/git/TreeHouse/web_server/selected_ncbi_taxon_parent_rank_name.txt"
gtdb_taxonomy_file = "/Users/allan/git/TreeHouse/gtdb/bvbrc_gtbd_reference_taxonomy.txt"
tree_data = '.' #'../gtdb'
hostName = "localhost"
serverPort = 8080
bvbrcTaxonTrees = None
tree_data = sys.argv[1]

class TreeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        parsed = urlparse(self.path)
        path = parsed.path.lstrip('/')
        print("Parsed query = "+parsed.query)
        print("stripped path = "+path)
        if os.path.isfile(path):
            print("found file "+path)
            with open(path) as file_to_serve:
                self.wfile.write(bytes(file_to_serve.read(), "utf-8"))
            return
        elif path == 'taxon':
            taxon = parsed.query
            tree_html = bvbrcTaxonTrees.get_tree_html(taxon)
            self.wfile.write(bytes(tree_html, "utf-8"))
        elif (path == 'list') or not path:
            list_html = bvbrcTaxonTrees.get_tree_list_html()
            self.wfile.write(bytes(list_html, "utf-8"))
        else:
            self.wfile.write(bytes("<html><head><title>Uninterpretable Request</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            self.wfile.write(bytes("<p>path: %s</p>" % path, "utf-8"))
            self.wfile.write(bytes("<p>query: %s</p>" % parsed.query, "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))
        return

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
        annotation['bvbrc_name'] = self.genome_name
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
    file_of_tree_files = sys.argv[1]

    bvbrcTaxonTrees = BvbrcTaxonTrees(bvbrc_name_lineage_file, ncbi_parent_rank_name_file, gtdb_taxonomy_file, file_of_tree_files)
    print("Files available:")
    files = os.listdir()
    for f in files:
        if (os.path.isfile(f)):
            print("file: {}".format(f))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        webServer.server_close()
        print("Server stopped.")

