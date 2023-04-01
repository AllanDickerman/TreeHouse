# web server for GTDB trees
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
import glob

tree_data_dir = '.' #'../gtdb'
hostName = "localhost"
serverPort = 8080
gtdbData = None
input_tree = sys.argv[1]

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
        elif path == 'tree':
            query_parts = parsed.query.split("&")
            tree = query_parts[0]
            taxon = None
            stop_rank = None
            for part in query_parts[1:]:
                if part.startswith("taxon="):
                    taxon = part.split('=')[1]
                    print("   taxon={}".format(taxon))
                if part.startswith("stop_at="):
                    stop_rank = part.split('=')[1]
                    print("   stop_rank={}".format(stop_rank))
            tree_html = gtdbData.get_tree_html(tree, taxon, stop_rank)
            self.wfile.write(bytes(tree_html, "utf-8"))
        elif (path == 'list') or path == '':
            list_html = gtdbData.get_tree_list_html()
            self.wfile.write(bytes(list_html, "utf-8"))
        else:
            self.wfile.write(bytes("<html><head><title>Uninterpretable Request</title></head>", "utf-8"))
            self.wfile.write(bytes("<body>", "utf-8"))
            self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
            self.wfile.write(bytes("<p>path: %s</p>" % path, "utf-8"))
            self.wfile.write(bytes("<p>query: %s</p>" % parsed.query, "utf-8"))
            self.wfile.write(bytes("</body></html>", "utf-8"))
        return

def new_record(tag, start, nest_level):
    retval = {'tag':tag, 'start': start, 'nest_level':nest_level, 'max_nest_level': nest_level, 'name':'', 'end':start, 'num_tips':0, 'num_genera':0, 'num_families':0}
    return retval
        
class GtdbData:
    def __init__(self, data_dir, input_tree):
        self.trees = {}
        self.tree_taxon = {}
        if input_tree:
            tree_tag = os.path.basename(input_tree)
            tree_tag = tree_tag.replace(".tree", "")
            tree_tag = tree_tag.replace(".nwk", "")
            with open(input_tree) as F:
                tree = F.read().rstrip()
                self.trees[tree_tag] = tree
                self.index_tree(tree_tag, tree)
                print("got tree for {}, len {}, ex: {}\n".format('bac', len(tree), tree[0:20]))
        else:
            tree_files = glob.glob(data_dir+"/*tree")
            for file in tree_files:
                tree_tag = os.path.basename(file)
                tree_tag = tree_tag.replace(".tree", "")
                tree_tag = tree_tag.replace(".nwk", "")
                with open(data_dir+"/"+file) as F:
                    tree = F.read().rstrip()
                    self.trees[tree_tag] = tree
                    self.index_tree(tree_tag, tree)
                    print("got tree for {}, len {}, ex: {}\n".format(tree_tag, len(tree), tree[0:20]))


    def index_tree(self, tag, newick):
        self.tree_taxon[tag] = {}
        nest_level = 0
        record_by_nest = []
        print("newick=\n{}\n".format(newick))
        index = 0
        fresh_close = None
        while index < len(newick):
            char = newick[index]
            sys.stdout.write("s[{}]={} ".format(index, char))
            if char == ';':
                print(" end of newick, nl={}".format(nest_level))
                break
            if char == '(':
                if len(record_by_nest) < nest_level+1:
                    record_by_nest.append(None)
                record_by_nest[nest_level] = new_record(tag, index, nest_level)
                print(' nest_level {}'.format(nest_level))
                nest_level += 1
            elif char == ',':
                sys.stderr.write(" nestlevel={}, len(rbn)={}\n".format(nest_level, len(record_by_nest)))
            elif char == ')':
                nest_level -= 1
                record = record_by_nest.pop()
                sys.stdout.write(', nest_level {}, len(rbn)={}\n'.format(nest_level, len(record_by_nest)))
                record['end'] = index
                #data.append(record)
                fresh_close = record
            else: # name
                record = None
                if fresh_close:
                    record = fresh_close
                    print("fresh close, retrieve: {}".format(record))
                else:
                    record = new_record(tag, index, nest_level)
                    if len(record_by_nest) < nest_level+1:
                        record_by_nest.append(record)
                    else:
                        record_by_nest[nest_level] = record;
                    #data.append(record)
                    for rec in record_by_nest:
                        if 'max_nest_level' in rec:
                            rec['max_nest_level'] = max(nest_level, rec['max_nest_level'])
                        else:
                            rec['max_nest_level'] = nest_level
                        rec['num_tips'] = rec['num_tips'] + 1
                fresh_close = None
                in_squote = char == "'"
                for end in range(index+1, len(newick)):
                    endchar = newick[end]
                    sys.stdout.write(endchar)
                    if in_squote:
                        if endchar == "'":
                            in_squote = False
                            sys.stdout.write("|")
                    elif endchar in [')', ',', ';']:
                        sys.stdout.write("\n")
                        name = newick[index : end]
                        print("before regex: name={}".format(name))
                        m = re.match("(.*):(\d+\.\d+)$", name)
                        if m:
                            name = m.group(1)
                            branch_length = m.group(2)
                            record['branch_length'] = branch_length;
                        if name.startswith("'") and name.endswith("'"):
                            name = name.strip("'")
                        m = re.match("(\d+\.\d+):(.*)", name)
                        if m:
                            support = m.group(1)
                            name = m.group(2)
                            record['support'] = support
                            for taxon in name.split(";"):
                                taxon = taxon.strip() # blank space follows ;
                                self.tree_taxon[tag][taxon] = record
                                print(" saved record for taxon {}".format(taxon))
                                if taxon.startswith("g__"):
                                    for rec in record_by_nest:
                                        rec['num_genera'] = rec['num_genera'] + 1
                                if taxon.startswith("f__"):
                                    for rec in record_by_nest:
                                        rec['num_families'] = rec['num_families'] + 1

                        index = end - 1
                        record['end'] = end-1
                        record['name'] = name
                        break
                print("finalize: {}".format(record))
            index += 1
        return 

    def extract_named_subtree(self, tree_str, node_label):
        # use string functions to extract substring corresponding to labeled subtree
        label_index = tree_str.find(node_label+"'")
        if label_index == -1:
            label_index = tree_str.find(node_label+";")
        if label_index == -1:
            sys.stderr.write("label {} not found\n".format(node_label))
            return None
        end_of_subtree = 0
        for i in range(label_index, label_index+140):
            l = tree_str[i]
            #sys.stderr.write(l)
            if l in (')', ','):
                sys.stderr.write("\nfound end = {}\n".format(i))
                end_of_subtree = i
                break
        if not end_of_subtree:
            sys.stderr.write("\ncould not find end of subtree\n")
            return None
        num_open = 0
        start_of_subtree = -1
        for i in reversed(range(label_index)):
            l = tree_str[i]
            #sys.stderr.write(l)
            if l == ')':
                num_open += 1
            elif l == '(':
                num_open -= 1
                if num_open == 0:
                    sys.stderr.write("\nfound beginning of subtree = {}\n".format(i))
                    start_of_subtree = i
                    break
        if start_of_subtree < 0:
            sys.stderr.write("\ncould not find start of subtree, i = {}\n".format(i))
            return None
        return tree_str[start_of_subtree : end_of_subtree]+";"

    def get_tree_list_html(self):
        print("get_taxon_list()")
        #for taxon in self.tree_taxon:
            #print(tree_taxon[taxon])
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "</head><body>\n"
        retval += "<h3>GTDB Trees</h3>\n"
        for tree in sorted(self.trees):
            retval += "<p><a href='tree?{}'>{}</p>\n".format(tree, tree)

        retval += "<table>"
        retval += "<tr><th>Tree</th><th>Taxon</th><th>Tips</th><th>Genera</th><th>Families</th></tr>\n";
        for tree in sorted(self.trees):
            for taxon in sorted(self.tree_taxon[tree]):
                record = self.tree_taxon[tree][taxon]
                retval += "<tr><td onclick=\"window.location.href='taxon?{}'\">{}</td><td>{}</td><td onclick=\"window.location.href='taxon?{}&stop_at=genus'\">{}</td><td onclick=\"window.location.href='taxon?{}&stop_at=family'\">{}</td></tr>\n".format(taxon, taxon, record['num_tips'], taxon, record['num_genera'], taxon, record['num_families'])
        retval += "</table>\n"
        retval += "</html>\n"
        return retval

    def get_tree_html(self, tag, taxon=None, stop_rank=None):
        print("tree_data.show_gtdb_taxon_tree({} {} {})".format(tag, taxon, stop_rank))

        if taxon:
            if taxon in self.tree_taxon:
                record = self.tree_taxon[taxon]
                newick = self.trees[tag][record['start']:record['end']]
            else:
                return "<html>No taxon named {} found.</html>".format(taxon)
        else:
            newick = self.trees[tag]
            
        print("newick = "+newick)
        retval = "<html><head>\n"
        retval += "<link rel='stylesheet' href='tree_style.css'>\n"
        retval += "</head><body>\n"
        retval += "<h3>Tree {} {}</h3>\n".format(tag, taxon)

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
        #genome_species = self.get_gtdb_species(genome_ids)
        #tip_label = {'label': species}

        retval += "<script type='text/javascript' src='gtdb_tree.js'></script>\n";
        retval += "<script type='text/javascript'>\n";
        retval += "const newick_tree_string = \""+newick+"\";\n" 
        retval += "debug = true\n" 
        #retval += "const tip_label = "+json.dumps(tip_label, indent=4)+";\n"  
        if (stop_rank):
            retval += "\nstop_rank='"+stop_rank+"'\n"
        retval += "\ncreate_gtdb_tree(newick_tree_string)\n"
        retval += "\n</script>\n";
            
        retval += "</body></html>"
        return retval

if __name__ == "__main__":        
    webServer = HTTPServer((hostName, serverPort), TreeHandler)
    print("Server started http://%s:%s" % (hostName, serverPort))

    gtdbData = GtdbData(tree_data_dir, input_tree)
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

