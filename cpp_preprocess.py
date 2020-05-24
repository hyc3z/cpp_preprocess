import getopt
import re
import sys




def write_func(file, func_name, args, body, retval, commented=False):
    file.writelines("{}{} {} ({}) {}".format("//" if commented else "", retval, func_name, args, "{\n"))
    for line in body.split("\n"):
        file.writelines("{}{}{}".format("//" if commented else "", line, "\n"))
    file.writelines("{}{}\n".format("//" if commented else "", "}"))

def write_to_cache(cache, func_name, args, body, retval, commented=False):
    cache += "\n{}{} {} ({}) {}".format("//" if commented else "", retval, func_name, args, "{\n")
    for line in body.split("\n"):
        cache += "{}{}{}".format("//" if commented else "", line, "\n")
    cache += "{}{}\n".format("//" if commented else "", "}")
    return cache

def write_cache_to_file(file, cache):
    file.writelines(cache)

def write_extra(file, extracontent):
    try:
        file.writelines(extracontent+"\n")
    except Exception as e:
        print(e)


def task(source_file, output_file, retval, ptrval, argval, soname, err_retval, dep_funcs, template, rep_funcs):
    total_cache = ""
    check_dup = 0
    written_funcs = []
    if argval is None:
        argval = "unsigned int"
    if err_retval is None:
        err_retval = retval
    with open(output_file, "w+") as of:
        if template is None:
            content = """
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

static void *dev_handle = nullptr;


static void LoadLibrary() {{
    dev_handle = dlopen("/usr/lib/x86_64-linux-gnu/{}", RTLD_NOW | RTLD_LOCAL);
	if (!dev_handle) {{
		exit(1);
	}}
}}

template<typename T>
static T LoadSymbol(const char *symbol_name) {{
	if (!dev_handle) LoadLibrary();
	void *symbol = dlsym(dev_handle, symbol_name);
	return reinterpret_cast<T>(symbol);
}}

{} GetSymbolNotFoundError() {{
    // TO DO Return error.
	return ;
}}\n""".format(soname, err_retval)
        else:
            content = template+"\n"
        write_extra(of, content)
        for i in source_file:
            with open(i, 'r') as sf:
                print("Parsing file {} ...".format(i))
                check_dup += 1
                content = sf.read()
                func_names = re.findall("\n" + retval + " " + ptrval + " (.*?)\((.*?)\)", content, re.S)
                if len(func_names) == 0:
                    func_names = re.findall("\n" + retval + " (.*?)\((.*?)\)", content, re.S)
                if len(func_names) > 0:
                    for symbol in func_names:
                        extra_declaration = False
                        func_name = symbol[0].strip().replace("\t", "").replace("\n", "")
                        if func_name not in written_funcs:
                            written_funcs.append(func_name)
                            if check_dup > 1:
                                print("Found function {} which isn't found before.".format(func_name))
                                # extra_declaration = True
                        else:
                            # print("Function {} already added. Skipping.".format(func_name))
                            continue
                        args = symbol[1].strip().replace('\n', "").split(',')
                        types = []
                        full_args = []
                        for i in range(len(args)):
                            tmp = args[i].strip()
                            tmp = tmp.split(" ")
                            args[i] = tmp[-1] if tmp[-1] != "void" else ""
                            prefix = ""
                            for letter in args[i]:
                                if not letter.isalpha():
                                    prefix += letter
                                else:
                                    break
                            if len(prefix) > 0:
                                args[i] = args[i][len(prefix):]
                            typename = " ".join(tmp[:-1]) if not tmp[-1].startswith(prefix) else " ".join(
                                tmp[:-1]) + prefix
                            types.append(typename.strip())
                            if len(prefix) > 0 and typename.endswith(prefix) and args[i].startswith(prefix):
                                full_args.append("{} {}".format(typename[:-len(prefix)], args[i]).strip())
                            else:
                                full_args.append("{} {}".format(typename, args[i]).strip())
                        # print(func_name, args)
                        content = """using FuncPtr = {}({} *)({});
    static auto func_ptr = LoadSymbol<FuncPtr>("{}");
    if (!func_ptr) return GetSymbolNotFoundError();
    {} result = func_ptr({});
    return result;""".format(retval, ptrval, ",".join(types),
                                     func_name if func_name not in rep_funcs.keys() else rep_funcs[func_name],
                                     retval, ",".join(args))
                        if extra_declaration:
                            declaration = "{} {} ({});".format("{} {}".format(retval, ptrval) if ptrval is not None else retval, func_name, ",".join(full_args))
                            write_extra(of, declaration)
                        total_cache = write_to_cache(total_cache, func_name, ",".join(full_args), content,
                                   "{} {}".format(retval, ptrval) if ptrval is not None else retval,
                                   commented=func_name in dep_funcs)
        write_cache_to_file(of, total_cache)


def main(argv):
    source_file = []
    output_file = None
    retval = None
    ptrval = None
    argval = None
    soname = None
    errval = None
    dep_funcs = []
    rep_funcs = {}
    template = None
    usage = "{} -i <inputfile> -o <outputfile> -r <retval> -p <ptrval> -a <argval>".format(__file__)
    try:
        opts, args = getopt.getopt(argv, "hi:o:p:r:a:s:e:d:t:n:", ["ifile=", "ofile=", "ptrval=", "retval=", "argval=", "soname=", "errval=", "deprecated=", "template=", "replace="])
    except getopt.GetoptError:
        print(usage, "Err")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(usage)
            sys.exit()
        elif opt in ("-i", "--ifile"):
            source_file.append(arg)
        elif opt in ("-o", "--ofile"):
            output_file = arg
        elif opt in ("-r", "--retval"):
            retval = arg
        elif opt in ("-p", "--ptrval"):
            ptrval = arg
        elif opt in ("-a", "--argval"):
            argval = arg
        elif opt in ("-s", "--soname"):
            soname = arg
        elif opt in ("-e", "--errval"):
            errval = arg
        elif opt in ("-d", "--deprecated"):
            with open(arg) as dpfc:
                for i in dpfc.readlines():
                    dep_funcs.append(i.strip().replace('\n',"").replace("\r", "").replace("\t",""))
        elif opt in ("-t", "--template"):
            with open(arg) as tpfc:
                template = tpfc.read()
        elif opt in ("-n", "--replace"):
            with open(arg) as dpfc:
                for i in dpfc.readlines():
                    rep_match = i.strip().replace('\n',"").replace("\r", "").replace("\t","")
                    len_before = len(rep_match) + 1
                    len_after = len(rep_match)
                    while len_before != len_after:
                        len_before = len(rep_match)
                        rep_match = rep_match.replace("  ", " ")
                        len_after = len(rep_match)
                    rep_match = rep_match.split(" ")
                    for i in rep_match:
                        if i.startswith("#define"):
                            rep_match.remove(i)
                        if len(i) == 0:
                            rep_match.remove(i)
                    if len(rep_match) == 2:
                        rep_funcs[rep_match[0]] = rep_match[1]
                    else:
                        print("Warning: ignoring function replacement {}, error occured during process.".format(str(rep_match)))
    if source_file is not None and output_file is not None:
        task(source_file, output_file, retval, ptrval, argval, soname, errval, dep_funcs, template, rep_funcs)
    else:
        print(usage)
        sys.exit(2)


if __name__ == '__main__':
    main(sys.argv[1:])
