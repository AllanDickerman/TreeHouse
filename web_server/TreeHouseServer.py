# Python 3 server example
import sys
import re
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
import sqlite3
import subprocess
import os.path
import tempfile

tree_database_file = '../tree_house.db'
hostName = "localhost"
serverPort = 8080
treeData = None

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
        elif path == 'gtdb':
            tree_html = treeData.show_gtdb_tree(parsed.query)
            self.wfile.write(bytes(tree_html, "utf-8"))
        elif path == 'get_tree_static':
            split_query = parsed.query.split("&")
            tree_id = split_query[0]
            use_bvbrc = True
            if len(split_query) > 1:
                if split_query[1] == 'nobvbrc':
                    treeData.set_use_bvbrc(False)
                elif split_query[1] == 'bvbrc':
                    treeData.set_use_bvbrc(True)
            tree_html = treeData.show_tree(tree_id)
            self.wfile.write(bytes(tree_html, "utf-8"))
        elif path == 'get_tree':
            split_query = parsed.query.split("&")
            tree_id = split_query[0]
            tree_html = treeData.show_tree(tree_id, "dynamic")
            self.wfile.write(bytes(tree_html, "utf-8"))
        elif path == 'browse_taxa':
            self.wfile.write(bytes(treeData.generate_taxon_table(parsed.query), "utf-8"))
        elif path == '' or path == 'index' or len(parsed.path) == 0:
            index_string = treeData.generate_tree_table()
            self.wfile.write(bytes(index_string, "utf-8"))
        elif path == 'flag_tree_taxon':
            split_query = parsed.query.split("&")
            tree_id = split_query[0].split('=')[1]
            taxon_id = split_query[1].split('=')[1]
            treeData.flag_tree_taxon(tree_id, taxon_id)
        else:
            self.wfile.write(bytes("<html><head><title>Tree Server Response</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            self.wfile.write(bytes("<p>path: %s</p>" % path, "utf-8"))
            self.wfile.write(bytes("<p>query: %s</p>" % parsed.query, "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))

    def do_POST(self):
        print("Post raw path = "+self.path)
        if (self.path.startswith("/save_arranged_tree")):
            self.data_string = self.rfile.read(int(self.headers['Content-Length']))
            data = json.loads(self.data_string)
            print("data.tree_id={}, nwk='{}'".format(data['tree_id'], data['nwk']))
            treeData.save_arranged_tree(data['tree_id'], data['nwk'])
        self.send_response(200)
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:8080')
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write('{"status": "done"}'.encode(encoding='utf_8'))
        return



class TreeData:
    def __init__(self, database_file):
        self.tree_db_conn = sqlite3.connect(database_file)
        self.cur = self.tree_db_conn.cursor()
        self.trees = {}
        self.use_bvbrc = True
        self.cur.execute("SELECT rowid, name, num_tips, mean_dist FROM genome_tree ")
        records = self.cur.fetchall()
        for row in records:
            (row_id, name, num_tips, mean_dist)  = row
            if not mean_dist:
                mean_dist = 0
            self.trees[row_id] = {'name':name, 'num_tips': num_tips, 'mean_dist': mean_dist, 'num_homologs':0, 'arranged':False, 'taxa': {}}
        sys.stderr.write("got trees, num= {}\n".format(len(self.trees)))
        if (0):
            self.cur.execute("SELECT tree_id, newick FROM arranged_tree")
            records = self.cur.fetchall()
            for row in records:
                tree_id  = row[0]
                newick = row[1]
                if tree_id in self.trees:
                    self.trees[tree_id]['arranged'] = True
                    self.trees[tree_id]['newick'] = newick
                else:
                    print("got a tree_id not in the tree list: "+str(tree_id))
        
        self.canonical_taxon_tree = {}
        self.cur.execute("SELECT tree_id, taxon_id FROM flagged_tree_taxon")
        records = self.cur.fetchall()
        for row in records:
            (tree_id, taxon_id)  = row
            self.trees[tree_id]['canonical'] = taxon_id
            self.canonical_taxon_tree[taxon_id] = tree_id

        self.trees_for_taxon = {}
        self.taxon_name = {}
        self.taxon_rank = {}
        self.cur.execute("SELECT tree_id, count(*) FROM tree_homolog GROUP BY tree_id")
        records = self.cur.fetchall()
        for row in records:
            (tree_id, num_homologs)  = row
            self.trees[tree_id]['num_homologs'] = int(num_homologs)

        self.genome_name = {}
        self.cur.execute("SELECT genome_id, genome_name FROM genome")
        records = self.cur.fetchall()
        i = 0
        for row in records:
            (genome_id, genome_name)  = row
            self.genome_name[str(genome_id)] = genome_name
            i+=1
            if i < 5:
                print("self.genome_name[{}] = {}".format(genome_id, genome_name))
        print("number of genomes in data: {}".format(len(self.genome_name)))
        print("genome_name['1049789.4'] = {}".format(self.genome_name['1049789.4']))

        self.cur.execute("SELECT tree_id, tree_taxon.taxon_id, local_taxon.name, local_taxon.rank, num_tips, mean_dist FROM tree_taxon, local_taxon where local_taxon.taxon_id = tree_taxon.taxon_id and tree_taxon.taxon_id > 2 and not eclipsed order by num_tips desc") 
        records = self.cur.fetchall()
        for row in records:
            (tree_id, taxon_id, taxon_name, taxon_rank, num_tips, mean_dist)  = row
            self.trees[tree_id]['taxa'][taxon_id] = {'num_tips': num_tips, 'mean_dist': mean_dist}
            self.taxon_name[taxon_id] = taxon_name
            self.taxon_rank[taxon_id] = taxon_rank
            if taxon_id not in self.trees_for_taxon:
                self.trees_for_taxon[taxon_id] = []
            self.trees_for_taxon[taxon_id].append(tree_id)
        self.taxon_parent = {} # will accummulate data here as trees are requested
        self.taxon_name_rank = {} # will accummulate data here as trees are requested
        print(" len(trees_for_taxon): {}".format(len(self.trees_for_taxon)))
        
    def get_genome_names(self, genome_ids):
        print("number of genomes in data: {}".format(len(self.genome_name)))
        retval = {}
        for gid in genome_ids:
            if gid in self.genome_name:
                retval[gid] = self.genome_name[gid]
            else:
                print("did not find {} in self.genome_name".format(gid))
        return retval

    def get_gtdb_species(self, genome_ids):
        print("number of genomes in data: {}".format(len(self.genome_name)))
        retval = {}
        for gid in genome_ids:
            self.cur.execute("SELECT species FROM gtdb_genome_species where genome_id = '{}'".format(gid))
            row = self.cur.fetchone()
            if row:
                retval[gid] = row[0]
            elif gid in self.genome_name:
                retval[gid] = self.genome_name[gid]
        return retval

    def get_taxon_info(self, taxon_ids):
        taxon_parent = {}
        taxon_name_rank = {}
        taxa_needing_parent = set(taxon_ids)
        print('get_taxon_info, num needing parent: {}'.format(len(taxa_needing_parent)))
        while len(taxa_needing_parent):
            taxon = taxa_needing_parent.pop()
            if int(taxon) < 3:
                continue
            if str(taxon) not in self.taxon_parent:
                print("select taxon info for {}".format(taxon))
                records = self.cur.execute("SELECT taxon_id, parent_id, rank, name from local_taxon where taxon_id = ?", (taxon,))
                row = records.fetchone()
                if row:
                    (taxon_id, parent_id, rank, name) = row
                    print('{} {} {} {}'.format(taxon_id, parent_id, rank, name))
                    self.taxon_parent[str(taxon_id)] = str(parent_id)
                    self.taxon_name_rank[str(taxon_id)] = (name, rank)
            if str(taxon) in self.taxon_parent:
                taxon_parent[str(taxon)] = self.taxon_parent[str(taxon)]
                taxon_name_rank[str(taxon)] = self.taxon_name_rank[str(taxon)]
                taxa_needing_parent.add(taxon_parent[str(taxon)])
            else:
                print("{} not in self.taxon_parent!!".format(str(taxon)))
        return (taxon_parent, taxon_name_rank)


    def generate_tree_table(self):
        retval = "<html><head>\n";
        retval += "<link rel='stylesheet' href='tree_style.css'>\n";
        retval += "</head><body>\n"
        retval += "<h1>Tree List (number of trees = {})</h1>\n".format(len(self.trees))
        retval += "<button  onclick=\"window.location='browse_taxa'\">Browse Taxa</button>\n";
        retval += "<table>\n"
        retval += "<tr><th>ID</th><th>Name (link)</th><th>Num Tips</th><th>Mean Dist</th><th>Num Genes</th><th>Arranged</th></tr>\n";
        for tree_id in sorted(self.trees):
            canonical = ""
            if 'canonical' in self.trees[tree_id]:
                canonical = '&#10003;'  # code for a checkmark
            retval += "<tr><td>{}</td><td class='tree_link' onclick=\"window.location.href='get_tree?{}'\">{}</td><td>{}</td><td>{:.3f}</td>"\
                    .format(tree_id, tree_id, self.trees[tree_id]['name'], self.trees[tree_id]['num_tips'], self.trees[tree_id]['mean_dist'])
            retval += "</td><td>{}</td><td>{}</td></tr>\n".format(self.trees[tree_id]['num_homologs'], self.trees[tree_id]['arranged'])
        retval += "</table></html>\n"
        return retval

    def generate_taxon_table(self, target_taxon=None):
        print("treeData.generate_taxon_table( target_taxon = {})".format(target_taxon))
        if target_taxon:
            target_taxon = int(target_taxon)
        retval = "<html><head>\n";
        retval += "<link rel='stylesheet' href='tree_style.css'>\n";
        retval += "</head><body>\n"
        taxon_list = []
        print("{} in self.trees_for_taxon = {}".format(target_taxon, target_taxon in self.trees_for_taxon))
        if target_taxon and (target_taxon in self.trees_for_taxon):
            retval += "<button  class='taxon_link' onclick=\"window.location='browse_taxa'\">Browse All Taxa</button>\n"
            taxon_list = [target_taxon]
            retval += "<h1>Trees for Taxon {}</h1>\n".format(self.taxon_name[target_taxon])
        else:
            taxon_list = sorted(self.trees_for_taxon)
            retval += "<h1>Taxon List (number of taxa = {})</h1>\n".format(len(taxon_list))
        retval += "<button  onclick=\"window.location='index'\">Browse Trees</button>\n"
        retval += "<table>\n"
        retval += "<tr class='table_header'><td>Taxon Name</td><td>Tree ID</td><td>Can</td><td>Taxon <br>Occur</td><td>Tips on<br> Tree</td><td>Dist Within<br> Taxon</td><td>Mean Tree Dist</td></tr>\n"
        for taxon_id in taxon_list:
            taxon_name = self.taxon_name[taxon_id]
            trees_for_taxon = self.trees_for_taxon[taxon_id]
            tree_id = trees_for_taxon[0]
            canonical = ""
            if 'canonical' in self.trees[tree_id] and self.trees[tree_id]['canonical'] == taxon_id:
                canonical = '&#10003;'  # code for a checkmark
            taxon_tips = self.trees[tree_id]['taxa'][taxon_id]['num_tips']
            taxon_mean_dist = self.trees[tree_id]['taxa'][taxon_id]['mean_dist']
            retval += "<tr><td rowspan={}>{}</td><td class='tree_link' onclick=\"window.location.href='get_tree?{}'\">{}</td><td>{}</td><td>{}</td><td>{}</td><td>{:.4f}</td><td>{:.4f}</td></tr>\n".format(len(trees_for_taxon), taxon_name, tree_id, tree_id, canonical, taxon_tips, self.trees[tree_id]['num_tips'], taxon_mean_dist, self.trees[tree_id]['mean_dist'], )
            for tree_id in trees_for_taxon[1:]:
                canonical = ""
                if 'canonical' in self.trees[tree_id] and self.trees[tree_id]['canonical'] == taxon_id:
                    canonical = '&#10003;'  # code for a checkmark
                taxon_tips = self.trees[tree_id]['taxa'][taxon_id]['num_tips']
                taxon_mean_dist = self.trees[tree_id]['taxa'][taxon_id]['mean_dist']
                retval += "<tr><td class='tree_link' onclick=\"window.location.href='get_tree?{}'\">{}</td><td>{}</td><td>{}</td><td>{}</td><td>{:.4f}</td><td>{:.4f}</td></tr>\n".format(tree_id, tree_id, canonical, taxon_tips, self.trees[tree_id]['num_tips'], taxon_mean_dist, self.trees[tree_id]['mean_dist'])
        retval += "</table></html>\n"
        return retval

    def set_use_bvbrc(self, on_off):
        self.use_bvbrc = on_off
        print("treeData.set_use_bvbrc({})".format(on_off))

    def show_gtdb_tree(self, tree_file):
        print("tree_data.show_gtdb_tree(tree_file={})".format(tree_file))
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "</head><body>\n"
        if not os.path.exists("../gtdb/bvbrc_labeled_subtrees/"+tree_file):
            print("Tree {} does not exist.".format(tree_file))
            retval += "Tree {} does not exist.</html>\n".format(tree_file)
            return retval
        newick = None
        with open("../gtdb/bvbrc_labeled_subtrees/"+tree_file) as F:
            newick = F.read().rstrip()
        print("newick = "+newick)
        retval += "<h3>GTDB Tree {}</h3>\n".format(tree_file)

        retval += "<div id='tree_comment_dialog'><label for='comment_input'>Input comment:</label><textarea id='comment_input' name='comment_input' rows='8' cols='60'></textarea><br><button id='submit_comment' onclick='submit_tree_comment()'>Submit</button></div>\n"

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
        retval += "<option value='reroot'>Re-root Tree</option>\n"
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
        retval += "</select>\n"
        retval += "</td></tr></table>"

        retval += "<div id='svg_container' style='width: 800px; height: 600px; overflow-y: scroll;'>\n"
        retval += "</div>"

        #genome_taxon = {}
        genome_ids = re.findall("[(,]([^(),:]+)", newick)
        print("num genome IDs found = {}, sample = {}".format(len(genome_ids), genome_ids[:5]))
        genome_species = self.get_gtdb_species(genome_ids)
        #    genome_taxon[genome_id] = re.sub("\..*", "",  genome_id)
        #genome_name = self.get_genome_names(genome_taxon.keys())
        #(taxon_parent, taxon_info) = self.get_taxon_info(genome_taxon.values())
        tip_label = {'species': genome_species}

        retval += "<script type='text/javascript' src='gtdb_tree.js'></script>\n";
        retval += "<script type='text/javascript'>\n";
        retval += "const newick = \""+newick+"\";\n" 
        retval += "const tip_label = "+json.dumps(tip_label, indent=4)+";\n"  
        #retval += "const taxon_parent = "+json.dumps(taxon_parent, indent=4) +";\n"
        #retval += "const taxon_info = "+json.dumps(taxon_info, indent=4) +";\n"
        retval += "\nprocess_json_newick()\n"
        retval += "\n</script>\n";
            
        retval += "</body></html>"
        return retval


    def show_tree(self, tree_id, method='static'):
        print("tree_data.show_tree(tree_id={}, method={})".format(tree_id, method))
        tree_id = int(tree_id)
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "</head><body>\n"
        if tree_id not in self.trees:
            retval += "Tree {} does not exist in database.</html>\n".format(tree_id)
            return retval
        retval += "<h3>Tree <span id='tree_id'>{}</span> &nbsp; {}</h3>\n".format(tree_id, self.trees[tree_id]['name'])
        retval += "<button onclick=\"window.location='get_tree?{}'\">Next Tree</button> &nbsp; <button  onclick=\"window.location='index'\">Browse Trees</button> &nbsp; <button  class='taxon_link' onclick=\"window.location='browse_taxa'\">Browse Taxa</button> <button onclick='initiate_tree_comment({})'>Comment</button><p>\n".format(tree_id+1, tree_id)

        retval += "<div id='tree_comment_dialog'><label for='comment_input'>Input comment:</label><textarea id='comment_input' name='comment_input' rows='8' cols='60'></textarea><br><button id='submit_comment' onclick='submit_tree_comment()'>Submit</button></div>\n"

        retval += "<table>\n"
        retval += "<tr><th>Num Tips</th><th>Num Genes</th><th>Mean Dist.</th><th>Arranged</th><th>Can</th><tr>\n";
        mean_dist = 'NA'
        if 'mean_dist' in self.trees[tree_id] and self.trees[tree_id]['mean_dist']:
            mean_dist = "{:.3f}".format(self.trees[tree_id]['mean_dist'])
        canonical = ""
        if 'canonical' in self.trees[tree_id]:
            canonical = '&#10003;'  # code for a checkmark
        retval += "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><tr>\n".format(self.trees[tree_id]['num_tips'], self.trees[tree_id]['num_homologs'], mean_dist, self.trees[tree_id]['arranged'], canonical) 
        retval += "</table><p>\n"
        if len(self.trees[tree_id]['taxa']):
            retval += "<b>Taxa in Tree {}</b>\n".format(tree_id)
            #retval += "<div style='width: 800px; height: 200px; overflow-y: scroll;'>\n"
            retval += "<table id='TreeTaxa'>\n"
            retval += "<thead><tr class='table_header'><th>{}</th><th>{}</th><th>{}</th><th>{}</th><tr></thead>\n".format('Taxon', 'Number', 'Mean Distance', 'Canonical')
            retval += '<tbody>\n'
            for taxon_id in self.trees[tree_id]['taxa']:
                taxon_data = self.trees[tree_id]['taxa'][taxon_id]
                canonical = ""
                if 'canonical' in self.trees[tree_id] and self.trees[tree_id]['canonical'] == taxon_id:
                    canonical = '&#10003;'  # code for a checkmark
                retval += "<tr><td class='taxon_link' onclick=\"window.location='browse_taxa?{}'\">{}</td><td onclick='highlight_taxon({})'>{}</td><td onclick=\"flag_tree_taxon({}, {})\">{:.3f}</td><td>{}</td></tr>\n".format(taxon_id, self.taxon_name[taxon_id], taxon_id, taxon_data['num_tips'], tree_id, taxon_id, taxon_data['mean_dist'], canonical) 
            retval += '</tbody>\n'
            retval += "</table>\n"
            retval += "<p>"
            #retval += "</div><p>"
        else:
            retval += "No taxa are annotated.\n"

        retval += "<table><td>"
        retval += "<label for='annotation_field_select'>Label:</label><br>\n"
        retval += "<select id='annotation_field_select'>\n"
        retval += "</select>\n"
        retval += "&nbsp;";
        retval += "</td><td>\n";
        retval += "<label for='node_action_select'>Node Action</label><br>\n"
        retval += "<select id='node_action_select'>\n"
        retval += "<option value='highlight'>Highlight Nodes</option>\n"
        retval += "<option value='swap'>Swap Children</option>\n"
        retval += "<option value='reroot'>Re-root Tree</option>\n"
        retval += "<option value='newick'>Newick Subtree</option>\n"
        retval += "</select>\n"
        retval += "&nbsp;";
        retval += "</td><td>\n";
        retval += "<label for='global_action_select'>Global Action</label><br>\n"
        retval += "<select id='global_action_select' onchange='global_action()'>\n";
        retval += "<option value='generate_newick'>Generate Newick</option>\n"
        retval += "<option value='save_arrangement'>Save Arrangement</option>\n"
        retval += "<option value='list_highlighted'>List Highlighted</option>\n"
        #retval += "<option value='generate_json_newick'>Generate Json Newick</option>\n"
        retval += "<option value='order_tree_up'>Order Tree Up</option>\n"
        retval += "<option value='order_tree_down'>Order Tree Down</option>\n"
        retval += "</select>\n"
        retval += "</td></tr></table>"

        retval += "<div id='svg_container' style='width: 800px; height: 600px; overflow-y: scroll;'>\n"
        if method == 'static':
            retval += self.get_tree_as_svg(tree_id)
        retval += "</div>"
        if method == 'static':
            retval += "<script type='text/javascript' src='svg_tree.js'></script>\n"
        else: # dynamic

            newick = None
            self.cur.execute(f"SELECT newick FROM arranged_tree where tree_id = ?", (tree_id,))
            row = self.cur.fetchone()
            if row:
                newick = row[0]
            else:
                self.cur.execute(f"SELECT newick FROM genome_tree where rowid = ?", (tree_id,))
                newick = self.cur.fetchone()[0]
            newick = newick.rstrip() # some trees have line returns
            print("newick = "+newick)
            genome_taxon = {}
            for genome_id in re.findall("[(,]([^(),:]+)", newick):
                genome_taxon[genome_id] = re.sub("\..*", "",  genome_id)
            genome_name = self.get_genome_names(genome_taxon.keys())
            (taxon_parent, taxon_info) = self.get_taxon_info(genome_taxon.values())
            tip_label = {'genome_name': genome_name, 'taxon': genome_taxon}

            retval += "<script type='text/javascript' src='dynamic_svg_tree.js'></script>\n";
            retval += "<script type='text/javascript'>\n";
            retval += "const newick = \""+newick+"\";\n" 
            retval += "const tip_label = "+json.dumps(tip_label, indent=4)+";\n"  
            retval += "const taxon_parent = "+json.dumps(taxon_parent, indent=4) +";\n"
            retval += "const taxon_info = "+json.dumps(taxon_info, indent=4) +";\n"
            retval += "\nprocess_json_newick()\n"
            retval += "\n</script>\n";
            
        retval += "</body></html>"
        return retval

    def get_tree_as_svg(self, tree_id):
        print("tree_data.get_tree_as_svg(tree_id={})".format(tree_id))
        tree_id = int(tree_id)
        tree_name = self.trees[tree_id]['name']
        #svgFile = f"tree_web_{tree_name}.svg"
        #if not os.path.exists(svgFile):
        self.cur.execute(f"SELECT name, newick FROM genome_tree where rowid = {tree_id}")
        (tree_name, newick_string) = self.cur.fetchone()
        self.cur.execute(f"SELECT newick FROM arranged_tree where tree_id = {tree_id}")
        (arranged_tree) = self.cur.fetchone();
        if (arranged_tree):
            print("found arranged tree for id {}".format(tree_id))
            newick_string = arranged_tree[0]

        #newickFile = f"tree_web_{tree_name}.nwk"
        #with open(newickFile, 'w') as n:
        #    n.write(newick_string+"\n")
        print(newick_string)
        command=['p3x-reformat-tree', '--output_format', 'svg']
        if (self.use_bvbrc):
            command.extend(('-l', 'genome_id', '-g', 'genome_name,family,order'));
        sys.stderr.write("command = "+" ".join(command)+"\n")
        #return_code = subprocess.call(command, shell=False) 
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        proc.stdin.write(bytes(newick_string, "utf-8"))
        proc.stdin.close()
        svg_string = proc.stdout.read()
        return svg_string.decode('ASCII')

    def save_arranged_tree(self, tree_id, arranged_nwk):
        print("save_arranged_tree({}, {})".format(tree_id, arranged_nwk[:20]))
        self.cur.execute("SELECT count(*) from arranged_tree WHERE tree_id=?", (tree_id,))
        existing_tree = self.cur.fetchone()[0]
        print("existing tree({})".format(existing_tree))
        if (existing_tree):
            self.cur.execute("UPDATE arranged_tree set newick = ? WHERE tree_id = ?", (arranged_nwk, int(tree_id)))
        else:
            self.cur.execute("INSERT INTO arranged_tree (tree_id, newick) VALUES (?, ?)", (int(tree_id), arranged_nwk))
        self.tree_db_conn.commit()

    def flag_tree_taxon(self, tree_id, taxon_id):
        print("treeData.flag_tree_taxon({}, {})".format(tree_id, taxon_id))
        self.cur.execute("select tree_id from flagged_tree_taxon where taxon_id = ?", (taxon_id,))
        existing_tree = self.cur.fetchone()
        if existing_tree:
            self.cur.execute("UPDATE flagged_tree_taxon SET tree_id = ? where taxon_id = ?", (int(tree_id), int(taxon_id)))
        else:
            self.cur.execute("INSERT INTO flagged_tree_taxon (tree_id, taxon_id) VALUES (?, ?)", (int(tree_id), int(taxon_id)))

    def create_tree_comment(self, tree_id, comment, author):
        print("create_tree_comment({}, {})".format(tree_id, comment[:34]))
        self.cur.execute("insert into tree_comment (tree_id, author, body, date, priority)", (tree_id, author, comment, datetime.datetime.now(), 1))

if __name__ == "__main__":        
    webServer = HTTPServer((hostName, serverPort), TreeHandler)
    print("Server started http://%s:%s" % (hostName, serverPort))

    treeData = TreeData(tree_database_file)
    print("Files available:")
    files = os.listdir()
    for f in files:
        if (os.path.isfile(f)):
            print(f"file: {f}")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        webServer.server_close()
        print("Server stopped.")

