import os,sys,time,json,tempfile,subprocess
from pathlib import Path
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,GLib,Gdk,Gio
MARK='Koplyx E2E : été, € et texte exact 2026-09-25'
def pump(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        while GLib.MainContext.default().iteration(False): pass
        time.sleep(.01)
def xd(*args):
    return subprocess.check_output(['xdotool',*map(str,args)],text=True).strip()
if len(sys.argv)>1 and sys.argv[1]=='target':
    win=Gtk.Window(title='Cible audit Koplyx'); entry=Gtk.Entry();entry.set_text(MARK);win.set_child(entry);win.set_default_size(650,120);win.present();entry.grab_focus()
    def save():
        Path(sys.argv[2]).write_text(entry.get_text());return True
    GLib.timeout_add(80,save);GLib.MainLoop().run();sys.exit()
root=Path(tempfile.mkdtemp(prefix='koplyx-e2e-'))
for k,v in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_RUNTIME_DIR','runtime')]:
    p=root/v;p.mkdir(mode=0o700);os.environ[k]=str(p)
os.environ['GSETTINGS_BACKEND']='memory'
sys.path.insert(0,'/home/limax/Documents/Koplyx')
from koplyx import main as m
wm=subprocess.Popen(['xfwm4','--compositor=off'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
target=None;app=None
try:
    pump(1)
    app=m.KoplyxApplication();assert app.register(None);app.hold();app.config.set('onboarding_completed',True);app.config.set('paste_backend','xorg');app.ensure_window()
    state=root/'target.txt'
    target=subprocess.Popen(['/usr/bin/python3',__file__,'target',str(state)])
    pump(1)
    wid=xd('search','--name','^Cible audit Koplyx$').splitlines()[-1]
    xd('windowactivate','--sync',wid);xd('key','ctrl+a','ctrl+c');pump(1.4)
    entries=app.store.recent();assert len(entries)==1,entries
    item=entries[0];assert app.store.payload(item.id)[2].decode()==MARK
    print('PASS copie clavier dans application cible -> capture -> stockage chiffre',flush=True)
    assert MARK.encode() not in (m.DATA_DIR/'history.db').read_bytes()
    xd('key','BackSpace');pump(.2);assert state.read_text()==''
    app.window.present();pump(.3);app.previous_window_id=wid
    row=app.window.listbox.get_first_child();app.window.listbox.emit('row-activated',row)
    pump(1.8)
    if state.read_text()!=MARK:
        print('FAIL collage automatique: champ='+repr(state.read_text())+' statut='+app.status_message,flush=True)
        xd('windowactivate','--sync',wid);pump(.2);xd('key','--window',wid,'--clearmodifiers','ctrl+v');pump(.6)
        print('DIAGNOSTIC xdotool --window sur cible active: '+repr(state.read_text()),flush=True)
        xd('key','ctrl+a','BackSpace');pump(.2);xd('key','--clearmodifiers','ctrl+v');pump(.6)
        assert state.read_text()==MARK,repr(state.read_text())
        print('PASS Ctrl+V classique sur cible active: texte exact restaure',flush=True)
    else:
        print('PASS collage automatique dans cible GTK',flush=True)
    assert len(app.store.recent())==1
    print('PASS absence de doublon apres restauration',flush=True)
    app.window.search.set_text('été');app.refresh();assert len(app.display_items())==1
    app.window.search.set_text('introuvable');app.refresh();assert len(app.display_items())==0
    app.window.search.set_text('');app.refresh();row=app.window.listbox.get_first_child();row.on_pin(None);app.window.set_active_view('pinned');assert len(app.display_items())==1
    print('PASS recherche contenu et onglet epingles',flush=True)
    settings=m.SettingsWindow(app,app.window)
    def walk(w):
        yield w
        c=w.get_first_child()
        while c:
            yield from walk(c);c=c.get_next_sibling()
    assert m.APP_VERSION in [w.get_text() for w in walk(settings) if isinstance(w,Gtk.Label)]
    settings.destroy();print('PASS version affichee dans Parametres',flush=True)
    app.window.set_active_view('history')
    # Donnees image et fichier publiees sur le vrai presse-papiers GDK.
    pix=m.GdkPixbuf.Pixbuf.new(m.GdkPixbuf.Colorspace.RGB,True,8,2,2);pix.fill(0x22aa44ff)
    texture=Gdk.Texture.new_for_pixbuf(pix);clip=Gdk.Display.get_default().get_clipboard();clip.set_content(Gdk.ContentProvider.new_for_value(texture));pump(1.4)
    assert any(i.kind=='image' for i in app.store.recent());print('PASS capture image via presse-papiers GDK',flush=True)
    f=root/'fichier-test.txt';f.write_text('preuve E2E');clip.set_content(Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list([Gio.File.new_for_path(str(f))])));pump(1.4)
    assert any(i.kind=='file' for i in app.store.recent());print('PASS capture fichier via presse-papiers GDK',flush=True)
    # Restauration des formats, sans demander une insertion dans un editeur texte.
    for kind in ['image','file']:
        print('DEBUT restauration '+kind,flush=True);i=next(i for i in app.store.recent() if i.kind==kind);app.config.set('paste_backend','portal');os.environ['XDG_SESSION_TYPE']='wayland';app.restore_item(i.id);print('retour restore_item '+kind,flush=True);pump(.2)
        values=[]
        if kind=='image':
            clip.read_texture_async(None,lambda c,r: values.append(c.read_texture_finish(r)))
        else:
            clip.read_value_async(Gdk.FileList.__gtype__,GLib.PRIORITY_DEFAULT,None,lambda c,r: values.append([f.get_uri() for f in c.read_value_finish(r).get_files()]))
        pump(.4);assert values and values[0] is not None
        if kind=='image': assert values[0].get_width()==2
        else: assert values[0]==[f.as_uri()]
    print('PASS restauration image et fichier lus par API presse-papiers',flush=True)
    print('Textes du profil test: '+repr([app.store.payload(i.id)[2].decode() for i in app.store.recent() if i.kind=='text']),flush=True);before_reload=[(i.id,i.kind) for i in app.store.recent()];print('Elements avant reouverture: '+repr(before_reload),flush=True);reloaded=m.HistoryStore(m.CryptoBox(),m.Config());assert [(i.id,i.kind) for i in reloaded.recent()]==before_reload;assert reloaded.payload(item.id)[2].decode()==MARK;reloaded.conn.close()
    print('PASS reouverture base et cle: elements persistants',flush=True)
    app.window.set_active_view('pinned');row=app.window.listbox.get_first_child();row.on_delete(None);assert len(app.store.recent())==len(before_reload)-1
    app.store.clear();assert app.store.recent()==[];print('PASS suppression unitaire et effacement profil test',flush=True)
    print('PARCOURS ISOLE TERMINE: consulter les lignes PASS et FAIL',flush=True)
finally:
    if target: target.terminate();target.wait(timeout=5)
    if app:
        app.control_server.close();app.store.conn.close();app.quit()
    wm.terminate();wm.wait(timeout=5)
    import shutil;shutil.rmtree(root)
