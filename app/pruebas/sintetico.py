"""Genera un CASO SINTÉTICO grande (.xghc) con nombres inventados — NO procede de ningún centro real.

Unos 85 profesores, 33 grupos, 85 aulas, 1 marco de 5 días × 7 tramos lectivos (+ recreo), sesiones con
distribuciones fijas (1111, 111, 21, 11, 2, 1) y variables, bloques de optativas simultáneas, aulas fijas y
alternativas por conjuntos, prohibiciones de profesores, guardias AC (en recreos) y GU (lectivas),
~25 reuniones (departamentos, tutores de cada curso, CCP...) y complementarias.

Uso: sintetico.py [salida.xghc] [semilla]
"""
import sys, os, random
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _rutas as _R
from horarios import xghc

PLANTILLA = os.path.join(_R.R, "prueba1.xghc")   # solo se reutilizan el contenedor, tareas, criterios y otros


def sub(p, tag, text=None, **at):
    e = ET.SubElement(p, tag, {k: str(v) for k, v in at.items()})
    if text is not None:
        e.text = str(text)
    return e


def generar(salida, semilla=7, enorme=False):
    """enorme=True: ~120 profesores y 45 grupos (prueba de escalado del motor)."""
    NPROF = 120 if enorme else 85
    rnd = random.Random(semilla)
    cont = xghc.leer_contenedor(PLANTILLA)
    base = ET.fromstring(cont.xml)
    raiz = ET.Element("datosGHC")
    sub(raiz, "version", base.findtext("version"))
    # ---------------------------------------------------------- marco: 5 días × 8 tramos (recreo en el 4º)
    md = sub(raiz, "marcosDeHorario"); mh = sub(md, "marcoHorario", id="A", nombre="Marco A", claveX="A")
    horas = [("08:30", "09:25", "lectivo"), ("09:25", "10:20", "lectivo"), ("10:20", "11:15", "lectivo"),
             ("11:15", "11:45", "recreo"), ("11:45", "12:40", "lectivo"), ("12:40", "13:35", "lectivo"),
             ("13:35", "14:30", "lectivo"), ("14:30", "15:25", "lectivo")]
    k = 0
    for d in range(5):
        for i, (a, b, t) in enumerate(horas):
            k += 1; tr = sub(mh, "tramo")
            for tag, v in (("submarco", "A"), ("dia", d), ("indice", i), ("horaEntrada", a + ":00"),
                           ("horaSalida", b + ":00"), ("Tipo", t), ("clavX", k)):
                sub(tr, tag, v)
    LECT = [i for i, h in enumerate(horas) if h[2] == "lectivo"]
    # ---------------------------------------------------------- grupos y aulas
    grupos = []
    reparto = ((("1ESO", 8), ("2ESO", 8), ("3ESO", 8), ("4ESO", 8), ("1BAC", 6), ("2BAC", 6), ("1FPB", 1)) if enorme else
               (("1ESO", 6), ("2ESO", 6), ("3ESO", 6), ("4ESO", 6), ("1BAC", 4), ("2BAC", 4), ("1FPB", 1)))
    for curso, n in reparto:
        for j in range(n):
            grupos.append((curso, f"SINT {curso} {'ABCDEFGH'[j]}"))
    especiales = {"SINT Laboratorios": 4, "SINT Informática": 5, "SINT Gimnasios": 3, "SINT Música": 2,
                  "SINT Plástica": 3, "SINT Tecnología": 3, "SINT Idiomas": 4}
    if enorme:
        especiales = {c: n + max(1, n // 3) for c, n in especiales.items()}
    aulas = [f"SINT Aula {g.split(' ', 1)[1]}" for _, g in grupos]          # 33 aulas de grupo
    conj = {}
    for c, n in especiales.items():
        conj[c] = [f"{c} {i + 1}" for i in range(n)]; aulas += conj[c]       # 24
    conj["general"] = [f"SINT Desdoble {i + 1:02d}" for i in range(40 if enorme else 28)]; aulas += conj["general"]   # 28 -> 85
    ax = sub(raiz, "aulas")
    for a in aulas:
        e = sub(ax, "aula"); sub(e, "nombre", a); sub(e, "dedicada", "false"); sub(e, "plantilla")
    ca = sub(raiz, "conjuntoDeAulas")
    for c, l in conj.items():
        e = sub(ca, "general" if c == "general" else "otroConjunto", nombre=c, **({"sinDeclarar": 0} if c == "general" else {}))
        for a in l:
            sub(e, "aula", a)
    raiz.append(base.find("tareas"))
    for t in raiz.find("tareas").findall("tarea"):
        pass
    # ---------------------------------------------------------- materias por curso (horas, departamento, conjunto)
    M = {"LEN": ("Lengua", 4, None), "MAT": ("Matemáticas", 4, None), "ING": ("Idiomas", 3, "SINT Idiomas"),
         "GEH": ("Sociales", 3, None), "BYG": ("Ciencias", 3, "SINT Laboratorios"), "FYQ": ("Ciencias", 3, "SINT Laboratorios"),
         "EF": ("EdFisica", 2, "SINT Gimnasios"), "MUS": ("Musica", 2, "SINT Música"), "PLA": ("Plastica", 2, "SINT Plástica"),
         "TEC": ("Tecnologia", 2, "SINT Tecnología"), "TUT": ("Orientacion", 1, None), "REL": ("Religion", 1, None),
         "FRA": ("Idiomas", 2, None), "INF": ("Tecnologia", 2, "SINT Informática"), "FIL": ("Filosofia", 3, None),
         "HIS": ("Sociales", 3, None), "ECO": ("Economia", 4, None), "LAT": ("Clasicas", 4, None),
         "DIB": ("Plastica", 4, "SINT Plástica"), "OPT": ("Varios", 3, None), "FPB": ("FP", 6, "SINT Tecnología")}
    plan = {"1ESO": ["LEN", "MAT", "ING", "GEH", "BYG", "EF", "MUS", "PLA", "TUT", "REL", "FRA", "TEC"],
            "2ESO": ["LEN", "MAT", "ING", "GEH", "FYQ", "EF", "MUS", "TEC", "TUT", "REL", "FRA", "PLA"],
            "3ESO": ["LEN", "MAT", "ING", "GEH", "BYG", "FYQ", "EF", "TEC", "TUT", "REL", "FRA", "INF"],
            "4ESO": ["LEN", "MAT", "ING", "GEH", "EF", "TUT", "REL", "INF"],
            "1BAC": ["LEN", "MAT", "ING", "FIL", "EF", "INF"],
            "2BAC": ["LEN", "ING", "HIS", "FIL", "TUT"],
            "1FPB": ["FPB", "FPB", "LEN", "MAT", "ING", "EF", "TUT"]}
    # optativas simultáneas (bloques) por curso: lista de materias que se imparten a la vez a todos los grupos
    optat = {"4ESO": [["BYG", "ECO", "LAT"], ["FYQ", "TEC", "PLA"]], "1BAC": [["MAT", "LAT", "DIB"], ["FYQ", "ECO", "HIS"]],
             "2BAC": [["MAT", "LAT", "DIB"], ["FYQ", "ECO", "GEH"], ["BYG", "OPT", "INF"]]}
    depts = sorted({v[0] for v in M.values()})
    dx = sub(raiz, "departamentos")
    for d in depts:
        e = sub(dx, "departamento"); sub(e, "nombre", d); sub(e, "nombreCompleto", f"Departamento sintético de {d}")
    # ---------------------------------------------------------- profesores por departamento según la carga
    carga = {d: 0 for d in depts}
    for curso, g in grupos:
        for s in plan[curso]:
            carga[M[s][0]] += M[s][1]
    for curso, bloques in optat.items():
        ng = sum(1 for c, _ in grupos if c == curso)
        for b in bloques:
            for s in b:
                carga[M[s][0]] += M[s][1] * max(1, ng // 2)
    total = sum(carga.values())
    nprof = {d: max(1, round(NPROF * carga[d] / total)) for d in depts}
    while sum(nprof.values()) > NPROF:
        d = max(nprof, key=lambda x: nprof[x] - NPROF * carga[x] / total); nprof[d] -= 1
    while sum(nprof.values()) < NPROF:
        d = max(nprof, key=lambda x: NPROF * carga[x] / total - nprof[x]); nprof[d] += 1
    profes = {d: [f"SINT-{d[:3].upper()}-{i + 1:02d}" for i in range(nprof[d])] for d in depts}
    uso = {p: 0 for l in profes.values() for p in l}
    MAXH = 20

    def elegir(d, h):
        cands = sorted(profes[d], key=lambda p: (uso[p], rnd.random()))
        p = next((p for p in cands if uso[p] + h <= MAXH), cands[0])
        uso[p] += h; return p
    # ---------------------------------------------------------- sesiones
    sl = sub(raiz, "sesionesLectivas"); sid = 0; bloques_xml = []; tutores = {}

    def dist(h, mat):
        if h == 6:
            return [2, 2, 2]
        if mat in ("BYG", "FYQ") and h == 3:
            return [2, 1]
        if mat == "DIB" and h == 4:
            return [2, 2]
        return [1] * h

    def sesion(mat, grupo, otros, prof, h, aula=None, alternativa=None, variable=False, fija=None):
        nonlocal sid
        s = sub(sl, "sesion", id=sid); sid += 1
        sub(s, "materia", mat); sub(s, "grupo", grupo); sub(s, "profesor", prof); sub(s, "duracionSemanal", f"{h:.2f}")
        ds = sub(s, "distribucionSemanal")
        if variable:
            dv = sub(ds, "distribucionVariable"); sub(dv, "numSesiones", f"{h:.2f}"); sub(dv, "numMaximoDeSesiones", 3)
            sub(dv, "penalizarSesionesSueltas", "penalizado")
        else:
            df = sub(ds, "distribucionFija")
            for n in (fija or dist(h, mat)):
                sub(df, "numSesiones", n)
        la = sub(s, "listaDeAulas")
        if aula:
            sub(la, "aula", aula)
        lal = sub(s, "listaDeAlternativas")
        if alternativa:
            sub(lal, "conjunto", alternativa)
        sub(s, "tarea", "LEC"); sub(s, "departamento", M[mat][0])
        op = sub(s, "opciones")
        sub(op, "penaSesionesAPrimera", "true" if mat == "EF" else "false"); sub(op, "penaSesionesAUltima", "false")
        sub(op, "permitirImpartanEnDiasSeguidos", "preferiblemente"); sub(op, "considerarLunesViernesSeguidos", "true")
        sub(s, "plantilla")
        og = sub(s, "otrosGrupos")
        for g in otros:
            sub(og, "grupo", g)
        return s.get("id")

    asign = {}
    for curso, g in grupos:
        aula_g = f"SINT Aula {g.split(' ', 1)[1]}"
        vistos = set()
        for mat in plan[curso]:
            d, h, cj = M[mat]
            if mat in vistos:          # FPB doble: misma materia, se agrupa
                continue
            n = plan[curso].count(mat); h = h * n
            p = elegir(d, h)
            if mat == "TUT":
                tutores[g] = p
            sesion(mat, g, [], p, h, aula=None if cj else aula_g, alternativa=cj,
                   variable=(mat == "FPB"))
            vistos.add(mat)
    for curso, bls in optat.items():
        gs = [g for c, g in grupos if c == curso]
        for bi, bl in enumerate(bls):
            # cada optativa: los grupos del curso se reparten en tantas secciones como optativas (desdobles)
            ids = []
            h = 3                                   # las simultáneas comparten distribución (111)
            for mat in bl:
                d, _h, cj = M[mat]
                p = elegir(d, h)
                ids.append(sesion(mat, gs[0], gs[1:], p, h, alternativa=cj or "general", fija=[1, 1, 1]))
            bloques_xml.append((curso, bi, ids))
    # ---------------------------------------------------------- profesores (con algunas prohibiciones)
    px = sub(raiz, "profesores")
    todos = [p for d in depts for p in profes[d]]
    dep_de = {p: d for d in depts for p in profes[d]}
    for i, p in enumerate(todos):
        e = sub(px, "profesor"); sub(e, "nombre", p); sub(e, "nombreCompleto", f"Profesor sintético {p}")
        sub(e, "departamento", dep_de[p]); pl = sub(e, "plantilla")
        r = rnd.random()
        if r < 0.15:       # una tarde/mañana libre: último tramo de un día prohibido
            dd = rnd.randrange(5)
            for idx in LECT[-2:]:
                sub(pl, "tramo", "prohibido", dia=dd, indice=idx, marco="A")
        elif r < 0.35:     # no preferentes a primera hora
            for dd in range(5):
                sub(pl, "tramo", "preferentementeNo1", dia=dd, indice=0, marco="A")
        op = sub(e, "opciones"); sub(op, "eliminarHuecos", "true")
    # materias
    mx = sub(raiz, "materias")
    for m_, (d, h, cj) in M.items():
        e = sub(mx, "materia"); sub(e, "nombre", m_); sub(e, "nombreCompleto", f"Materia sintética {m_}")
        sub(e, "departamento", d); sub(e, "plantilla")
    cx = sub(raiz, "cursos")
    for c in plan:
        e = sub(cx, "curso"); sub(e, "nombre", c); sub(e, "nombreCompleto", f"Curso sintético {c}")
    gx = sub(raiz, "grupos")
    for c, g in grupos:
        e = sub(gx, "grupo", submarco="A"); sub(e, "nombre", g); sub(e, "cursoPerteneciente", c)
        sub(e, "profesorTutor", tutores.get(g, "")); sub(e, "aula", f"SINT Aula {g.split(' ', 1)[1]}")
        pl = sub(e, "plantilla")
        if c in ("1ESO", "2ESO"):       # los pequeños no tienen 7ª hora
            for dd in range(5):
                sub(pl, "tramo", "prohibido", dia=dd, indice=LECT[-1], marco="A")
    raiz.find("sesionesLectivas")  # ya creado
    # mover sesionesLectivas detrás de grupos (orden del esquema)
    raiz.remove(sl); raiz.append(sl)
    lr = sub(raiz, "listasDeRelacion"); sim = sub(lr, "simultaneas")
    for curso, bi, ids in bloques_xml:
        b = sub(sim, "bloqueDeSesiones", id=ids[0], submarco="A"); ss = sub(b, "sesiones")
        for x in ids:
            sub(ss, "sesion", x)
        sub(b, "plantilla")
    # ---------------------------------------------------------- reuniones (~25)
    rx = sub(raiz, "reuniones"); nreu = 0

    def reunion(nombre, integrantes, doble=False):
        nonlocal nreu
        e = sub(rx, "reunion", subMarco="A"); sub(e, "nombre", nombre); sub(e, "numeroDeReuniones", 1)
        sub(e, "dobleDuracion", "true" if doble else "false"); sub(e, "tipoDeTarea", "RDP"); sub(e, "lectiva", "false")
        sub(e, "plantilla"); ig = sub(e, "integrantes")
        for p in integrantes:
            sub(ig, "integrante", p)
        nreu += 1
    for d in depts:
        if len(profes[d]) >= 2:
            reunion(f"Dpto {d}", profes[d])
    for c in plan:
        tut = [tutores[g] for cc, g in grupos if cc == c and g in tutores]
        if tut:
            reunion(f"Tutores {c}", sorted(set(tut)))
    jefes = [profes[d][0] for d in depts]
    reunion("CCP", jefes, doble=False)
    reunion("Equipo directivo", [todos[0], todos[10], todos[20]], doble=True)
    reunion("Convivencia", [todos[5], todos[15], todos[25], todos[35]])
    reunion("Biblioteca", [todos[7], todos[17], todos[27]])
    reunion("Proyecto bilingüe", [p for p in profes.get("Idiomas", [])[:3]] + [todos[40], todos[50]], doble=True)
    # ---------------------------------------------------------- guardias AC (recreos) y GU (lectivas)
    gux = sub(raiz, "guardias")
    for nombre, recreo, cant, nper in (("GU", False, 8 if enorme else 5, None), ("AC", True, 10 if enorme else 8, 1)):
        e = sub(gux, "guardia", subMarco="A"); sub(e, "nombre", nombre); sub(e, "tipoDeTarea", "G")
        sub(e, "enRecreos", "true" if recreo else "false"); sub(e, "lectiva", "false")
        pc = sub(e, "profesoresACadaHora"); sub(pc, "cantidad", cant)
        ig = sub(e, "integrantes")
        for p in todos:
            n = nper if nper else (2 if uso[p] <= 10 else 1)
            if recreo and rnd.random() < 0.6:
                continue
            it = sub(ig, "integrante"); sub(it, "nombre", p); sub(it, "numeroDeGuardias", n); sub(it, "plantilla")
        sub(e, "plantilla")
    # ---------------------------------------------------------- complementarias
    cmx = sub(raiz, "complementarias")
    for i, p in enumerate(jefes):
        e = sub(cmx, "complementaria", subMarco="A"); sub(e, "identificador", i); sub(e, "tarea", "DIR" if i < 3 else "JD")
        sub(e, "profesor", p); sub(e, "lectiva", "false"); sub(e, "plantilla")
        sub(e, "intervalosSemanales", 3 if i < 3 else 2); sub(e, "maxIntervalosDiarios", 1); sub(e, "noConsecutivos", "true")
    raiz.append(base.find("criterios")); raiz.append(base.find("otros"))
    ET.indent(raiz, "\t")
    cuerpo = ET.tostring(raiz, encoding="unicode")
    xml = (b'<?xml version="1.0" encoding="ISO-8859-1"?>\n<!-- CASO SINTETICO generado por pruebas/sintetico.py: '
           b'datos inventados, no corresponden a ningun centro real -->\n' + cuerpo.encode("iso-8859-1", "xmlcharrefreplace") + b"\n")
    with open(salida, "wb") as f:
        f.write(xghc.empaquetar(cont, xml))
    stats = {"profesores": len(todos), "grupos": len(grupos), "aulas": len(aulas), "sesiones": sid,
             "periodos": sum(uso.values()), "max_horas_prof": max(uso.values()), "reuniones": nreu,
             "bloques_simultaneas": len(bloques_xml), "tramos_lectivos_dia": len(LECT)}
    return stats


if __name__ == "__main__":
    enorme = "--enorme" in sys.argv; args = [a for a in sys.argv[1:] if a != "--enorme"]
    out = args[0] if args else os.path.join(_R.R, "SINTETICO_grande.xghc")
    print(generar(out, int(args[1]) if len(args) > 1 else 7, enorme))
    from horarios import validacion
    p = xghc.cargar(out)
    print("cargado:", len(p.profesores), "profesores,", len(p.grupos), "grupos,", len(p.aulas), "aulas,",
          len(p.sesiones), "sesiones,", len(p.reuniones), "reuniones,", len(p.guardias), "guardias")
    msgs = validacion.validar(p)
    print("validación:", {t: sum(1 for m in msgs if m[0] == t) for t in {m[0] for m in msgs}})
