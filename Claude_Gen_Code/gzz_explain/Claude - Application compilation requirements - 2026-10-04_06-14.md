# Application compilation requirements

**Exported with:** [AI Chat Exporter](https://ai-chat-exporter.covai.org)  
**Source:** Claude  
**Date:** 10/4/2026, 6:14:14 AM  
**Link:** [https://claude.ai/chat/993afc79-a5a2-4508-8fe1-5d105df2e25d](https://claude.ai/chat/993afc79-a5a2-4508-8fe1-5d105df2e25d)  
**Model:** claude-sonnet-5-5  
**Method:** API  

## Prompt:
What are the minimum requirements for compilation of this application?

## Response:
This is the build file for GZigZag, an old Java project. For a default `make all`, you need the following.

**Required tools**
- **GNU make.** The first line of the Makefile says so, and it uses GNU-only features like `$(wildcard)`, `$(foreach)`, `ifeq` and `:=`.
- **A Java compiler.** The Makefile uses `jikes +P` if `jikes` is on your PATH, and plain `javac` otherwise. You can force one with `make JAVAC=javac`.
- **Perl.** It's used to turn `.zob` files into `.java` files (`zob2java.pl`) and to build the source list.
- **Standard Unix utilities:** `sh`, `sed`, `sort`, `uniq`, `tee`, `rm`, `mv`, `date`, `whoami`, `hostname` and `which`. It also writes a scratch file to `/tmp/foo`.

**Required source layout**
- The Makefile expects to sit in the `Java/` directory of the source tree, next to `zob2java.pl`, `BuildInfo.java.in`, and the `clang/`, `storage/`, `media/`, `flob/` and other source directories.
- The `../Modules/` directory must contain every module listed in `MODULES`, and `clang/` must contain the `heraclitus` and `flowing` directories.

**Where it may fail**
- The default module list (applet, joystick, 3d, xml, extern and others) may need third-party libraries or APIs, such as Java 3D, a joystick library or an XML parser. The Makefile doesn't say which, and the comment at the top suggests removing modules if compilation fails.
- To reduce the requirements, override the lists on the command line, for example `make MODULES="" GREEKCLANG=""`. Whether the core compiles without any modules depends on the code, which I can't tell from the Makefile.
- The Makefile warns that you may need to run `make` more than once because of dependency ordering.
- This is early-2000s code (CVS, jikes), so a modern JDK may reject some of the source. The Makefile doesn't pin a Java version.

**Only for optional targets**
- `make opengl` needs `gltt`.
- `make doc` and `make zobdoc` need `javadoc`.
- `make jar` needs `jar` and `../makedist.sh`.
- `make tags` needs `ctags`.
- `make ncss` needs javancss at a hardcoded path.
- `make ChangeLog` needs `cvs2cl`.

## Prompt:
what possible upgrades are needed for compilation on modern Java?

## Response:
I've only seen the Makefile, not the Java source, so the first group below is what the Makefile itself shows. The second is what typically breaks in code of this age, and I haven't confirmed any of it.

**Changes to the Makefile and build process**
- **Force `javac`.** If `jikes` is on your PATH, the Makefile prefers it. Jikes is long dead and can't handle anything past Java 1.4-era syntax, so pass `JAVAC=...` explicitly.
- **Pin the language level.** Modern `javac` defaults to the newest level, and old source may use `assert`, `enum` or `_` as identifiers, which are now keywords. Old `-source 1.3` and `1.4` settings no longer work, and the oldest level modern JDKs accept is 8. Use `--release 8` first (or `-source 8 -target 8` if the code touches `sun.*` internals).
- **Set the source encoding.** JDK 18 and later default to UTF-8. This code has Greek and German module names, so comments and strings may be ISO-8859-1 and will produce "unmappable character" errors. Add `-encoding ISO-8859-1`.
- **Fix `javadoc`.** `make zobdoc` uses `-doclet org.gzigzag.ZobDoc`, written against the old `com.sun.javadoc` API, which was removed in JDK 13. That doclet would need porting to `jdk.javadoc.doclet`. For plain `make doc`, add `-Xdoclint:none`, since modern javadoc is much stricter about malformed HTML in comments.
- **Check native code.** The `arch/` directories use their own `arch.mk`. If they use JNI, `javah` was removed in JDK 10 and `javac -h` replaces it.
- **Check the Perl scripts.** `zob2java.pl` and the other `.pl` files haven't been run on modern Perl. Possible breakages are `require "file.pl"` relying on `.` in `@INC` (removed in 5.26), unescaped `{` in regexes, and `defined(@array)`.

A starting command would be:

```
make JAVAC="javac -encoding ISO-8859-1 --release 8" MODULES="" GREEKCLANG=""
```

Then add modules back one at a time.

**Likely source-level breakage**
- **`applet` module:** the Applet API has been deprecated for removal since JDK 17 and is being removed in the newest releases, so this module is a candidate to drop or rewrite.
- **Removed APIs:** `sun.misc.BASE64Encoder`, `com.sun.image.codec.jpeg` (a possibility in `media/`), `javax.xml.bind`, CORBA and `java.awt.peer`.
- **`SecurityManager`:** deprecated for removal and disabled by default, so applet-era code that installs one will fail at runtime.
- **`Thread.stop()`, `suspend()` and `resume()`:** these either throw or have been removed in recent JDKs.
- **Third-party libraries:** `3d` (probably Java 3D, which is not in the JDK), `joystick` (native), and `xml` (if it imports Xerces or Crimson classes directly) need external dependencies you'd have to supply on the classpath.
- **AWT 1.1-era methods** like `show()`, `hide()` and `handleEvent()` are deprecated, but I believe most still exist, so expect warnings rather than errors.
- **Raw types** (pre-generics collections) will compile with warnings only.

The quickest path is to try JDK 8, since it's the most forgiving, to get a working baseline. Then move up to a newer JDK and fix what breaks. If you upload the source or paste the first batch of compiler errors, I can be much more specific.

## Prompt:
Looking at this source code, what is a feasible project to extract the functionality of these objects?



### Attachment: ZZModule.java _(3.0 KB)_
````
/*   
ZZModule.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.awt.*;
import java.util.*;
import java.io.*;

/** An extension module implementing some Java functionality.
 * Extension module classes should have a single static public member
 * named <code>module</code> of this type.
 * <p>
 * Clang commands implemented in extension modules are accessed
 * through the Module.FUNCTION interface.
 */

public abstract class ZZModule {
String rcsid = "$Id: ZZModule.java,v 1.14 2000/10/30 15:25:47 tjl Exp $";

    /** Perform an action.
     * For instance, if the action Foo.BAR is used in a cell, the method
     * org.gzigzag.module.Foo.module.action("BAR",...) is called.
     * @param id The name of the action.
     * @param code The cell that the code was obtained from.
     * @param target The cell that is the target of the action. Either the
     * 			cell the cursor is on, or the cell that the user clicked
     * 			on with the mouse.
     * @param view The view the user activated this action from
     * @param cview The control view associated
     * @param key The event identifier
     * @param pt The point clicked by the mouse
     * @param xi The ZZScene describing the current contents of the window.
     * 		 May be used e.g. to draw XOR cursors.
     */
    public void action(String id,
	    ZZCell code, 
	    ZZCell target,
	    ZZView view, ZZView cview, String key, Point pt, ZZScene xi) {
    }

    /** Returns a ZOb for the given id.
     * A cell parameter is not needed: since it's a ZOb, the caller must
     * explicitly read them (and set the Component) after getting it.
     * @see ZOb
     */
    public ZOb newZOb(String id) { return null; }

    // Static routines for loading

    static Hashtable mods = new Hashtable();
    
    /** Obtain the ZZModule object corresponding to the given string.
     * This is the <b>module</b> member of the corresponding class.
     */
    static public ZZModule getModule(String name) {
	ZZModule m;
	if((m= (ZZModule)mods.get(name)) == null) {
	    try {
		Class clazz = Class.forName("org.gzigzag.module."+name);
		m = 
			(ZZModule)clazz.getField("module").get(null);
	    } catch(Exception e) {
		ZZLogger.exc(e);
		ZZLogger.log("Error while loading module '"+name+"'");
		return null;
	    }
	    mods.put(name, m);
	}
	return m;
    }

}

````



### Attachment: ZZObs.java _(1.1 KB)_
````
/*   
ZZObs.java
 *    
 *    Copyright (c) 1999-2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */

package org.gzigzag;
/** A simple class that observes something.
 * This class cannot distinguish what caused the event - either
 * the event has to be filtered prior to this or the whole thing reread
 * in any case.
 */

public interface ZZObs {
String rcsid = "$Id: ZZObs.java,v 1.11 2000/09/19 10:31:58 ajk Exp $";
    /** Called when something is changed.
     */
    void chg();
}

````



### Attachment: ZZObsTrigger.java _(6.2 KB)_
````
/*   
ZZObs.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka, queuing and enable/disable by Rauli Ruohonen
 */

package org.gzigzag;
import java.util.*;

/** A class used to trigger ZZObses.
 */

public class ZZObsTrigger {
String rcsid = "$Id: ZZObsTrigger.java,v 1.6.2.1 2001/04/08 16:13:59 ajk Exp $";
    public static boolean dbg = false;
    private static void p(String s) { if(dbg) ZZLogger.log(s); }
    private static void pa(String s) { ZZLogger.log(s); }
    
    // XXX Store weak references, not hard ones!
    private static Vector allTrigs = new Vector();
    private static Hashtable obsQueue = new Hashtable();
    private static Hashtable obsDisabled = new Hashtable();

    ZZObsTrigger() {
	allTrigs.addElement(this);
    }

    /** An object which keeps track of the observations of a single
     * ZZObs.
     */
    class Gob {
	/** Linked list of Gobs, plus list of all objects that this
	 * Gob observes.
	 * This is a tricky part and this is also what makes us blazingly
	 * fast. And difficult to explain. 
	 * <p>
	 * First of all, there is a key for every object that this
	 * gob's <code>obs</code> has been <code>addObs</code>'ed for.
	 * The value depends on whether there are other gobs observing
	 * the same thing. If there are, then the hashtables form a linked
	 * list. If not, or if this is the last element of the linked 
	 * list, the value in the Hashtable is <strong>this gob</strong>.
	 * That may seem odd until you realize that 1) hashtables can't
	 * store nulls, and 2) <code>this</code> is a pointer that is
	 * very likely to be in a register so fast to compare with
	 * the reference.
	 */
	Hashtable next = new Hashtable();
	/** The backward links. Only necessary links are stored. */
	Hashtable prev = new Hashtable();
	ZZObs obs;
    }

    /** Key: ZZObs; Value: Gob. */
    Hashtable gobs = new Hashtable();

    /** Key: Object (trigger); Value: Gob. */
    Hashtable trigs = new Hashtable();

    
    /** Called when something is changed.
     * This call removes instances of the ZZObses triggered from
     * <em>all</em> existing ZZObsTrigger objects.
     */
    public synchronized void chg(Object o) {
	Gob g,pg=null;
	Hashtable next=trigs;
	while((g = (Gob)next.get(o)) !=null && g!=pg) {
	    pg=g;
	    if(!chg(g.obs)) next=g.next;
	}
	// XXX This shouldn't be necessary! (views should use triggers)
	ZZUpdateManager.chg();
    }
    public static boolean chg(ZZObs obs) {
	// XXX This shouldn't be necessary! (views should use triggers)
	ZZUpdateManager.chg();
	synchronized(obsQueue) {
	    if(obsDisabled.containsKey(obs)) return false;
	    obsQueue.put(obs,obs);
	    for(int i=0; i<allTrigs.size(); i++)
		((ZZObsTrigger)allTrigs.elementAt(i)).rmObs(obs); 
	}
	return true;
    }

    /** Called to add an observer.
     */
    public synchronized void addObs(Object o, ZZObs obs) {
	Object go = gobs.get(obs);
	Gob g;
	if(go==null) {
	    gobs.put(obs, g = new Gob());
	    g.obs = obs;
	} else {
	    g = (Gob)go;
	}
	if(g.next.get(o) != null) return; // Already observing.
	Gob t = (Gob)trigs.get(o);
	trigs.put(o, g);
	if(t==null) g.next.put(o,g); // First observer for this object.
	else {
	    g.next.put(o,t);
	    t.prev.put(o,g);
	}
    }

    /** Called to remove observers.
     */
    public synchronized void rmObs(ZZObs obs) {
	Gob g = (Gob)gobs.get(obs);
	if(g == null) return; // Wasn't observing anything
	gobs.remove(obs);
	for(Enumeration e = g.next.keys(); e.hasMoreElements(); ) {
	    Object o = e.nextElement();
	    Gob ng = (Gob)g.next.get(o);
	    Gob pg = (Gob)g.prev.get(o);
	    if(pg==null) {
		if(ng==g) trigs.remove(o);
		else {
		    trigs.put(o,ng);
		    ng.prev.remove(o);
		}
	    } else {
		if(ng==g) pg.next.put(o,pg);
		else {
		    pg.next.put(o,ng);
		    ng.prev.put(o,pg);
		}
	    }
	}
    }

    /** Does the actual triggering.
     * XXX We must continue triggering until no new triggers are created,
     * which is bad if there are lots of (or infinite amount, in case of a
     * bug) triggers. This is because we must run triggers in the AWT event
     * processing thread (+), and unless we use JDK 1.2 "EventQueue.invoke*()"
     * methods or resort to some horrid dummy-event kludge, we can't expect
     * any triggers we leave behind to be triggered until the next AWT event,
     * which is unacceptable. ("- See, it doesn't display the new info if I
     * don't move the mouse around! - Are you *sure* it isn't a M$ product?")
     * This isn't a real problem at the moment, though.
     *
     * (+) The event thread must always be runnable, or we risk a deadlock,
     *     and most of ZZ structure -using code isn't thread-safe => only the
     *     event thread may call general ZZ structure -using code.
     */
    public static void runObsQueue() {
	p("runObsQueue enter");
	synchronized(obsQueue) {
	    while(obsQueue.size()>0) {
		p("STARTTRIGSEQ "+(obsQueue.size()));
		/* Trigger the queued observers in some order */
		Hashtable q=obsQueue;
		obsQueue=new Hashtable();
		for(Enumeration e=q.keys();e.hasMoreElements();)
		    try {
			((ZZObs)e.nextElement()).chg();
		    } catch(Exception ex) {
			ZZLogger.exc(ex);
			System.out.println("EXCEPTION WHILE TRIGGERING!");
		    }
		p("ENDTRIGSEQ "+(obsQueue.size()));
	    }
	}
	p("runObsQueue leave");
    }

    /** Enable/disable an observer.
     * If an observer is disabled, chg(o) won't trigger it. chg(o) calls
     * made before calling this method will be unaffected - that is, if
     * obs is in obsQueue, it will be triggered whether it is enabled or not.
     */
    public static void setEnabled(ZZObs obs,boolean t) {
	if(t) obsDisabled.remove(obs);
	else obsDisabled.put(obs,obs);
    }
}

````



### Attachment: ZZPath.java _(5.7 KB)_
````

/*   
ZZPath.java
 *    
 *    Copyright (c) 1999-2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/* Possibly publish this API later on? */
interface PathOp {
	/** Apply the pathop to the from cell, attaching the observer o
	 * to observe the relevant information about all the cells on the way.
	 * These objects do not need to attach observers to the from 
	 * cell but all the others, including the last cell.
	 * @return 	null if the requested cell does not exist.
	 */
	ZZCell apply(ZZCell from, ZZObs o);
}

/** A class to represent paths in the structure.
 * It used to also be a notifier but that was changed: now it's just
 * an abstract "path".
 */

public class ZZPath {
public static final String rcsid = "$Id: ZZPath.java,v 1.26 2000/10/18 14:35:31 tjl Exp $";
	static public boolean dbg = false;
	static final void p(String s) { if(dbg) System.out.println(s); }

	PathOp[] arr = new PathOp[0];

	public ZZPath() { }

	static final String drdim(ZZCell c) {
		return ZZDefaultSpace.getPossDerefCell(c).getText();
	}

	static final int drdir(ZZCell c) {
		String s = ZZDefaultSpace.getPossDerefCell(c).getText();
		if(s.equals("-")) return -1;
		if(s.equals("+")) return +1;
		return Integer.parseInt(s);
	}

	static final String drtext(ZZCell c) { return drdim(c); }

	/** Creates a ZZPath from cells.
	 * The cells give the path through a simple format in d.1 and d.2:
	 * The first cell is the operation name, and then follow the
	 * parameters, just like in the other calls for this class.
	 * <pre>
	 * 	STEP  dim  n
	 *	HEAD dim dir
	 *	END dim dir
	 *	FIND dim dir str
	 * </pre>
	 * Note that this is not automatically updated each time the path
	 * or the cursors in the path change - to be up to date, you need
	 * to create a new path each time. However, this is not such a 
	 * time-consuming operation.
	 *	<p>
	 * "HEAD" is now deprecated in favor of "END".
	 */
	static public ZZPath createFromStructure1(ZZCell c) {
	    ZZPath p = new ZZPath();
	    while(c!=null) {
		ZZCell[] args = c.readRank("d.1", 1, false);
		String s = c.getText();
		if(s.equals("STEP")) {
			if(args.length < 2)
			    throw new ZZError("Not enough args for '"+s+"'");
			p = p.step(drdim(args[0]), drdir(args[1]));
		} else if(s.equals("HEAD") || s.equals("END")) {
			if(args.length < 2)
			    throw new ZZError("Not enough args for '"+s+"'");
			p = p.headcell(drdim(args[0]), drdir(args[1]));
		} else if(s.equals("FIND")) {
			if(args.length < 3)
			    throw new ZZError("Not enough args for '"+s+"'");
			p = p.untilstring(drdim(args[0]),
				drdir(args[1]), drtext(args[2]));
		} else {
		    throw new ZZError("ZZPath syntax: '"+s+"'");
		}
		c = c.s("d.2", 1);
	    }
	    return p;
	}

	/** Reads the structure through this path to obtain a cell.
	 * @param from The cell to start from
	 * @param error Whether not finding a cell is an error.
	 * 		This is for coder convenience: the message
	 * 		in the exception thrown is descriptive of
	 *		where the not-found leg of the path was.
	 * @param o	The observer to attach.
	 */
	public ZZCell readFrom(ZZCell from, boolean error, ZZObs o) {
	    if(from == null)
		throw new ZZError("Can't read path from null!");
	    ZZCell n = from;
	    for(int i=0; i<arr.length; i++) {
		    n = arr[i].apply(n, o);
		    if(n==null) {
			    String s = "Couldn't find through ";
			    for(int j=0; j<i; j++)
				    s += arr[j];
			    s += "   Failed: ";
			    s += arr[i];
			    p(s);
			    if(!error)
				    return null;
			    throw new ZZError(s);
		    }
	    }
	    return n;
	}
	public ZZCell readFrom(ZZCell from, boolean error) {
	    return readFrom(from, error, null);
	}

	// XXX ??? A little odd down from here...
	// but basically right: ZZPath is immutable.

	/** Sign gives the direction on dim, absolute value
	 * number of steps */
	ZZPath step(final String dim, final int n) {
		return appendOp(new PathOp() {
			public ZZCell apply(ZZCell from, ZZObs o) {
				return from.s(dim, n, o);
			}
			public String toString() {
				return "step("+dim+","+n+")";
			}
		});
	}


	ZZPath headcell(final String dim, final int dir) {
		return headcell(dim, dir, false);
	}
	ZZPath headcell(final String dim, final int dir, final boolean ensuremove) {
		return appendOp(new PathOp() {
			public ZZCell apply(ZZCell from, ZZObs o) {
			    return from.h(dim, dir, 
				ensuremove, o);
			}
			public String toString() {
			    return "headcell("+dim+","+dir+","
				    +ensuremove+")";
			}
		});
	}

	ZZPath untilstring(final String dim, final int dir, final String str)
	{
		return appendOp(new PathOp()  {
			public ZZCell apply(ZZCell from, ZZObs o) {
			    return from.findText(dim, dir, str, o);
			}
			public String toString() {
			    return "untilstring("+dim+","+dir+",'"+str+"')";
			}
		});
	}

	ZZPath copy() {
		ZZPath n = new ZZPath();
		n.arr = new PathOp[arr.length];
		System.arraycopy(arr, 0, n.arr, 0, arr.length);
		return n;
	}

	ZZPath appendOp(PathOp p) {
		ZZPath n = new ZZPath();
		n.arr = new PathOp[arr.length + 1];
		System.arraycopy(arr, 0, n.arr, 0, arr.length);
		n.arr[arr.length] = p;
		return n;
	}


}


````



### Attachment: ZZPhotoView.java _(2.6 KB)_
````
/*   
ZZPhotoView.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 *  Patched to work with ZZViewComponend format by Jarkko Laine
 */

package org.gzigzag;
import java.awt.*;
import java.net.*;
import java.awt.event.*;

/** A simple view showing photos from the cursor.
 * This view shows the image at the URL on the end of d.photo from
 * the cell the cursor this view is associated with is on.
 */

public class ZZPhotoView extends ZZViewComponent {
public static final String rcsid = "$Id: ZZPhotoView.java,v 1.14 2000/11/01 08:12:48 tjl Exp $";
	ZZCell cursor;


        public ZZPhotoView(ZZCell viewCell0) {
                super(viewCell0);
	}

	URL cur;
	Image img;

	public boolean reraster() { return false; }

        public void paintInto(Graphics g) {


                
                // Clear the area
		Dimension thisd = getSize();
		Color bg = getBackground();
                g.setColor(bg);
		Insets ins = getInsets();
                g.fillRect(ins.left, ins.top, thisd.width-ins.left-ins.right, thisd.height-ins.top-ins.bottom);
                g.setColor(Color.black);



                // Let's try it like this.. Is this a bad way of doing this?
                cursor = ZZCursorReal.get(viewCell);


                // If the current cell has no neighbours in the
                // photo dimention..
		if(cursor == null ||
                   cursor.s("d.photo", 1) == null)
                {
                        Color c = Color.black;
                        g.setColor(c);

// For some weird reason, I can't get the drawStrings to work.... Jarkko

                        g.drawString("No photo for this cell", 0, 0);
		   	return;
		}
 

                

		URL url = null;
		try {
		url = new URL(cursor.h("d.photo", 1).getText());
		} catch(MalformedURLException e) {
			String s= e.toString();
                        g.drawString(s, 0, 0);
			return;
		}
		if(!url.equals(cur)) {
			cur = url;
			img = getToolkit().getImage(url);
		}
		if(!g.drawImage(img, 0, 0, null)) {
			repaint(1000);
		}
  
	}
}


````



### Attachment: ZZPrimitiveCommand.java _(2.7 KB)_
````
/* DO NOT EDIT THIS FILE. THIS FILE WAS GENERATED FROM ZZPrimitiveCommand.zob,
 * EDIT THAT FILE INSTEAD!
 * All changes to this file will be lost.
 */
/*   
ZZPrimitiveCommand.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Benjamin Fallenstein
 */

package org.gzigzag;
import java.awt.*;

/** A ZZCommand interface to ZZPrimitiveActions.
 */

public class ZZPrimitiveCommand extends ZZCommand implements ZOb {
		
    
    /** UNDOCUMENTED. 
 
 * <p>Default value: <PRE> null;</PRE>. 
 
 * @structparam 1 
 */ 

 public 
	ZZCell code
	    = null;
    

    /* AUTOGENERATED! */
    static final private int fullmask = 1;

    /* AUTOGENERATED! */
    public String readParams(ZZCell start) {
	int m = 0;
	try {
	    if(start != null)
		m = readParams(start, 0);
	} catch(Throwable t) {
	    ZZLogger.exc(t);
	} finally {
	    init__zob();
	}
	if((m & fullmask) != fullmask) {
	    // not all parameters present - no problem right now.
	}
	return "";
    }

    /* AUTOGENERATED! */
    private int readParams(ZZCell start, int mask) {
	ZZCell n = start;
	while(n != null) {
	    String s = n.getText();
	    // Tests autogenerated from members.
	    
	    if(s.equals("code")) {
		mask |= 1;
		try {
		    ZZCell c = n.s("d.1"); s = c.getText(); 
    {
    code = c;
    }
 
		} catch(Exception e) {
		    ZZLogger.exc(e);
		}
	    } else


	    { } // grab that last "else"
	    ZZCell h = n.h("d.3");
	    if(h != null && h != n) {
		// recurse
		mask |= readParams(h, mask);
	    }
	    n = n.s("d.2");
	}
	return mask;
    }



    protected void init__zob()  {
	if(code == null)
	    throw new ZZError("Must specify ZZPrimitiveCommand code!");
    }
		
    ZZPrimitiveActions pa = new ZZPrimitiveActions();

    public void execCallback(
		    ZZCell target,
		    ZZView view, 
		    ZZView cview,
		    String key,
		    Point pt, 
		    ZZScene xi
		     ) {
	pa.execCallback(code, target, view, cview, key, pt, xi);
    }

    public void exec(ZZCell param) {
	throw new ZZError("ZZPrimitiveCommand currently does not support "
			 +"primitives which aren't UI callbacks.");
    }
}
````



### Attachment: ZZRODimension.java _(1.5 KB)_
````
/*   
ZZRODimension.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** A read-only dimension.
 * This class simply extends ZZDimension by implementing the
 * abstract methods that would modify the dimension by code that
 * simply throws an exception.
 * The only method that subclasses will need to override is s.
 */

public abstract class ZZRODimension extends ZZDimension {
public static final String rcsid = "$Id: ZZRODimension.java,v 1.10 2000/11/05 19:11:13 tjl Exp $";
	public abstract ZZCellHandle s(ZZCellHandle c, int steps, ZZObs o); 
	public void connect(ZZCellHandle c, ZZCellHandle d) {
		throw new ZZError("Read-only dimension"); 
	}
	public void disconnect(ZZCellHandle c, int dir) {
		throw new ZZError("Read-only dimension"); 
	}
	public void excise(ZZCellHandle c) {
	    // Do nothing.
	}
}

````



### Attachment: ZZScene.java _(2.8 KB)_
````
/*   
ZZScene.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;
import java.awt.*;

/** An interface for obtaining clicked -objects based on coordinates.
 * This is what is given with mouse events.
 */

public interface ZZScene {
String rcsid = "$Id: ZZScene.java,v 1.4 2000/09/19 10:31:58 ajk Exp $";

    /** Get an identifying object for the given point on this canvas.
     * This is one point where OO decoupling doesn't work properly:
     * different things want to return different kinds of information:
     * CellThings want to return the cell, TextSpans a VStream.Pos and so on.
     */
    Object getObjectAt(int x, int y);

    /** Render this canvas, things interpolated with the given other canvas,
     * on the given graphics context. 
     * Interpolation is used for great advantage to show the user what the
     * relationship between two different states is, i.e. which cells
     * are the same. The modular nature of the ZZCanvas allows Things
     * to define their own interpolation semantics: for example, by default,
     * links are not rendered at all when interpolating and cells 
     * are interpolated linearly.
     */
    void renderInterp(Graphics g, ZZScene other, float fract);


    /** Paint a cursor-like thing using XOR.
     * Originally intended for drawing a ghost cursor on text when
     * moving the mouse in order to show where a click would put the cursor.
     */
    void renderXOR(Graphics g, int x, int y);

    /** Is interpolation to the given canvas visually useful.
     * This routine returns true if there is something in this canvas
     * which will be seen animated when interpolating to the new canvas.
     * For example, when only changing a dimension, some cells stay where
     * they are and all the others are replaced by other cells (usually... 
     * there are of course situations where some cells move on the screen
     * when changing a dimension). In this case, the user is better served
     * by not animating but simply displaying the new state as fast as
     * possible.
     */
    boolean isInterpUseful(ZZScene s2);

    /** Render this scene in the given graphics context.
     */
    void render(Graphics g);
}

````



### Attachment: ZZSlicedDimSpace.java _(3.2 KB)_
````
/*   
ZZSlicedDimSpace.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import org.gzigzag.*;
import java.util.*;

/** A space consisting of primitive slices.
 * NOTE: the current code does not support changing slice IDs
 * *AT ALL*.
 */

class EHSEFKUHESMFKMEFKLSEF { }

/*

public class ZZSlicedDimSpace extends ZZDimSpace {
public static final String rcsid = "$Id: ZZSlicedDimSpace.java,v 1.10 2000/11/07 23:07:33 tjl Exp $";
	
    static final String getOrigID(String c) {
	    return c.substring(c.indexOf('-')+1);
    }
    static final int getSliceID(String c) {
	    return Integer.parseInt(c.substring(0,c.indexOf('-')));
    }
    static final String getConvID(int sli, String ores) {
	    return ""+sli+"-"+ores;
    }

    ZZDimSpace[] slices;

    protected DimCell getNewCell(String id) {
	int sl = getSliceID(id);
	String or = getOrigID(id);
	DimCell ocell = slices[sl].getNewCell(or);
	id = getConvID(sl, ocell.getID());
	return (DimCell)getCellByID(id);
    }
    protected DimCell getNewCell() {
	throw new ZZError("Can't make new cells from nothing in sliced space");
    }

    public ZZSlicedDimSpace(ZZDimSpace[] s) {
	slices = s;
    }
    protected String getText(String id) {
	int sl = getSliceID(id);
	String or = getOrigID(id);
	ZZCell c = slices[sl].getCellByID(or);
	return c.getText();
    }

    protected Span getSpan(String id) {
	int sl = getSliceID(id);
	String or = getOrigID(id);
	ZZCell c = slices[sl].getCellByID(or);
	Span s = c.getSpan();
	return s;
    }
    protected void setText(String id, Object cont) {
	int sl = getSliceID(id);
	String or = getOrigID(id);
	ZZCell c = slices[sl].getCellByID(or);
	if(cont instanceof Span) {
	    c.setSpan((Span)cont);
	} else {
	    c.setText((String)cont);
	}
    }

    public ZZCell getHomeCell() {
	return getCellByID(getConvID(0, slices[0].getHomeCellID()));
    }

    public ZZDimension createDimension(String s) {
	if(s.equals("d.preflets")) return null;
	if(s.equals("d.slices")) return new SlicedHomes(this);
	if(s.equals("d.slicesame")) return new SlicedSame(this);
	ZZDimension[] dims = new ZZDimension[slices.length];
	for(int i=0; i<slices.length; i++)
	    dims[i] = slices[i].d(s);
	if(s.equals("d.cursor")) return new SlicedCursor(this, dims, "d.preflets");
	return new Sliced(this, dims);
    }

    // We delegate scroll creation to s.0
    // XXX Should scrolls be created to slices?
    public StringScroll getStringScroll() {
	return slices[0].getStringScroll();
    }

    public StringScroll getStringScroll(String name) {
	return slices[0].getStringScroll(name);
    }
}

*/

````



### Attachment: ZZSpace.java _(9.2 KB)_
````
/*   
ZZSpace.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka and Tuukka Hastrup
 */
/*
 * 	`He's got a good memory, you've got to grant him that,' said
 *    Didactylos. `Show him some more scrolls.'
 *	`How will we know he's remembered them?' Urn demanded, unrolling
 *    a scroll of geometrical theorems. `He can't read! And even if he 
 *    could read, he can't write!'
 *	`We shall have to teach him.'
 *		- Terry Pratchett, Small Gods, p.214
 */

package org.gzigzag;
import java.util.*;
/** A simple ZZ interface for a ZZ space.
 * This abstract class defines all the elementary operations
 * for a ZZ space. Note though, that many operations are done to
 * <b>cells</b> and are defined in ZZCell.java.
 * <p>
 * Also included are default operations for space. These can be overridden
 * in concrete implementations. Note how we can leave undecided witch 
 * classes and objects are responsible for some operations, as it's only
 * needed that the space contains all specified information.
 * <p>
 * The dimensions are listed in the space itself, on two ranks from 
 * the Home cell, along d.masterdim which includes all dimensions and
 * d.userdim which excludes the system dimensions that are generally
 * not used by the user (such as d.cursor, d.cursor-cargo). 
 * (XXX d.userdim not yet)
 * <p>
 * The event loop mechanism is included in this object since the
 * event loop is per-space. Currently, the way to prevent events
 * from propagating is to lock this object using synchronized(){}.
 * The relationship of this synchronization to remote objects is not
 * yet clear, as well as interaction with slices and such
 * so <b>this synchronization may change in the future
 * to a pair of freeze and thaw method calls</b>.
 */

public abstract class ZZSpace {
public static final String rcsid = "$Id: ZZSpace.java,v 1.22 2001/02/23 12:20:32 bfallenstein Exp $";
    public static boolean dbg = false;
    protected static void p(String s) { if(dbg) ZZLogger.log(s); }
    protected static void pa(String s) { ZZLogger.log(s); }

    // CORE FUNCTIONALITY OF ZZSPACE

    /** Obtain the unique ID for this space.
     * Note that this method <I>may not</I> throw an exception. 
     * if the space not have an ID.
     */
    public String getIDOrNull() {
        return null;
    }

    /** Obtain the unique ID for this space.
     * Note that this method <I>may</I> throw an exception,
     * if the space not have an ID.
     */
    public String getID() {
        String rv = getIDOrNull();
        if (rv == null) {
            throw new NullPointerException("This space has no valid ID");
        }
        return rv;
    }

    /** Set the unique ID for this space.
     * Note that this method <I>may</I> throw an exception
     * if the space does not support space IDs.
     */
    public void setID(String id) {
        throw new ZZError("Setting space ID not supported by this space");
    }

     /** Get the home cell of this space.
     * The home cell is where everything begins */
    abstract public ZZCell getHomeCell();

    /** Get a cell by its ID.
     */
    public ZZCell getCellByID(String s) {
	throw new ZZError("Not implemented for this space");
    }

    /** Get the appendable string scroll of this space.
     */
    public StringScroll getStringScroll() {
	return null;
    }
    /** Get the string scroll with the given identifier.
     * (XXX???)
     */
    public StringScroll getStringScroll(String name) {
	return null;
    }

    /** Find all cells whose span overlaps sp.
     */
    public ZZCell[] overlaps(Span sp) {
	return null;
    }


    // TIMESTAMP AND UNDO.
    // THESE NEED NOT DO ANYTHING.

    /** Timestamp the space.
     */
    public int stamp() {
	return -1;
    }
    /** Undo to the previous timestamp.
     */
    public void undo() {
    }
    /** Redo to the next timestamp.
     */
    public void redo() {
    }
    /** Commit the changes.
     * Commits may define their own timestamps i.e. after commit the
     * micro-level timestamps may not be accessible.
     */
    public int commit() {
	return -1;
    }


    // TRAVERSING

    /** Returns enumeration over the cells in this space - also in slices.
     */
    public Enumeration cells() {
	return new Enumeration() {
	    ZZCell next = getHomeCell();
	    ZZCell slice = next; // Homecell of current slice
	    public boolean hasMoreElements() {
		if(next == null)
		     return false;
		return true;
	    }
	    public Object nextElement() {
		if(next == null)
			throw new NoSuchElementException();
		ZZCell ret = next;
		next = next.s(d.cellcreation, 1);
		if(next == null) // End of this slice
			slice = next = 
			    slice.s(d.slices, 1);
		return ret;
	    }
	};
    }

    /** Get a list of the dimensions in the space.
     * This function will likely change in the future as it is possible
     * that dimensions become cells instead of strings.
     */ 
    public String[] dims() {
	Vector dims = new Vector();
	ZZCell c = getHomeCell().s(d.masterdim, 1);
	while(c != null) {
		dims.addElement(c.getText());
		c = c.s(d.masterdim, 1);
	}
	String[] ret = new String[dims.size()];
	for(int i = 0;i<dims.size();i++)
	    ret[i] = (String)dims.elementAt(i);
	return ret;
//	    return (String[])(dims.toArray(new String[dims.size()]));
    }


    // OBSERVING

    /** Freeze the space. No events are dispatched while 
     * the space is frozen. 
     */
    public void freeze() { }

    /** Thaw the space. No events are dispatched while 
     * the space is frozen. 
     */
    public void thaw() { }

    /** Remove all the cells from the observation list of this observer */
    abstract public void rmAllObs(ZZObs o);


    // VARIOUS

    /** Is this space readonly? FIXME: not used here */
    public /* final */ boolean readonly;

    public ZZSpace() { this(false); }
    public ZZSpace(boolean readonly) {
        this.readonly = readonly;
    }

    /** Finds the headcells of all ranks on dim
     * that are longer than one cell in length */
    public abstract ZZCell[] findLongRankHeads(String dim);


    // HANDLING OF MASTER DIM LIST

    /** Called when a new dimension is instantiated. It might be here already,
     *  however, as dimensions are instantiated again when the space is loaded
     *  from disk.
     *  @return		true iff dimension was truly new
     */
    protected boolean updateMasterDimList(String newdim) {
	if(!validDim(newdim))
	    return false;
	ZZCell p = getHomeCell().s(d.masterdim, 1);
	while(p!=null) { 
	    if(p.getText().equals(newdim))
		return false;
	    p = p.s(d.masterdim, 1);
	}
	ZZCell c = getHomeCell().N(d.masterdim, 1);
	c.setText(newdim);
	return true;
    }

    /** Recreate the master dimension list. */
    public void recreateMasterDimList() {
        throw new ZZError("recreateMasterDimList not implemented for this space");
    }

    /** Returns an enumeration of posward
     * connections on this dimension.
     * XXX Should change to be just ZZCells!!!
     */
    public Enumeration posconns(String dim) {
    	class ConnEnum implements Enumeration {
	    public ConnEnum(String dim) {
		this.dim = dim;
		next = findNext();
	    }
	    String dim;
	    Enumeration cells = cells();
	    ZZConnection next;
	    public boolean hasMoreElements() {
		if(next != null) 
		    return true;
		else
		    return false;
	    }
	    public Object nextElement() {
	    	if(next == null)
		    throw new NoSuchElementException();
		ZZConnection ret = next;
		next = findNext();
		return ret;
	    }
	    public ZZConnection findNext() {
	        while(cells.hasMoreElements()) {
		    ZZCell c1 = (ZZCell) cells.nextElement();

		    ZZCell c2 = c1.s(dim, 1);
		    if(c2 != null)
		    	return new ZZConnection(c1, dim, 1, c2);
		}
		return null;
	    }
	}
	return new ConnEnum(dim);
    }

    /** Whether a dimension name is acceptable.
     */
    public boolean validDim(String d) {
        if(d==null) return false;
        if(d.equals("")) return false;
        return true;
    }

    /** Class Dims acts as a structure containing concrete string representation
     *  of the special dimensions. It's not static so it can vary 
     *  between spaces. Also, these strings could be initialized in the 
     *  constructor to allow runtime setting.
     * <p>
     * This is going away once dimensions are cells, not strings.
     */
    class Dims {
	public final String cellcreation = "d.cellcreation";
        public final String slices = "d.slices";
	public final String masterdim = "d.masterdim";
        public final String clone = "d.clone";
    }

    /** A nice hack to make it possible to use d.* names. Contains all 
     *  dimensions witch have special meaning and are thus referenced 
     *  to in this class.
     */ 
    Dims d = new Dims();
}

````



### Attachment: ZZSpacePart.java _(3.1 KB)_
````
/*   
ZZSpacePart.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;

/** <b>EXPERIMENTAL:</b> A portion of a ZZ space.
 * This is a way to have some cells virtual, i.e. existing only
 * when called upon, and whose connections to other cells are algorithmic,
 * not stored.
 * <p>
 * For example, it is possible to make a huge tree-like calendar 
 * with thousands of years at nanosecond precision using these ideas:
 * the cell's ID in that part stores the data about the moment and
 * the dimensions give the movement from that cell to other cells.
 * <p>
 * Currently, cell IDs in part foo look like foo:... where ... is whatever
 * string that part wants to use.
 * Dimensions are like d.foo:... where ... is the name in the part.
 */

public abstract class ZZSpacePart {
public static final String rcsid = "$Id: ZZSpacePart.java,v 1.8 2001/03/08 13:37:16 ajk Exp $";
    public static boolean dbg = false;
    private static void p(String s) { if(dbg) ZZLogger.log(s); }
    private static void pa(String s) { ZZLogger.log(s); }

    /** The space part id. This is prepended to all the IDs of the cells
     * within this part. (DELIM??!!XXX)
     */
    public final String id;

    /** The space this part is a part of.
     */
    public final ZZDimSpace space;

    public ZZSpacePart(ZZSpace space, String id) {
	this.space = (ZZDimSpace)space;
	this.id = id;
    }

    /** Obtain a special dimension for this part.
     * The dimension name has the prefix stripped off.
     * This function may return null.
     */
    abstract public ZZDimension getDim(String name);

    /** The home cell for this space part.  This is useful in case
     * it's not connected to anywhere in the space proper. */
    public String homeID() { return null; }

    public String getText(ZZCellHandle c) { return ""; }
    public Span getSpan(ZZCellHandle c) { return null; }
    public void setContent(ZZCellHandle c, Object o) {
	// do nothing
    }

    public Object parseID(String id) {
	int ind = id.indexOf(':');
	if(ind < 0) throw new SyntaxError("No delimiter in ID");
	return parseIDPart(id.substring(ind+1));
    }
    abstract public Object parseIDPart(String idPart);

    public String toString() { return id; }

    public String generateID(Object parsed) {
	String rv = id + ":" + generateIDPart(parsed);
        return rv;
    }
    abstract public String generateIDPart(Object parsed);

    public ZZDimSpace.DimCell getCellByID(String s) { return null; }

    public void postCommitHook() {}
}


````



### Attachment: ZZTextView.java _(3.6 KB)_
````
/*   
ZZTextView.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka, rewritten to use AWT by Benja Fallenstein
 */
package org.gzigzag;
import java.awt.event.*;
import java.awt.*;

/** A text view showing the contents of one cell (the cursor).
 *  This is shown in a window of its own, using the AWT TextArea component,
 *  to allow copy-and-paste functions as you know them from PUIs. Basically,
 *  it's a dirty hack, because it's outside the usual GZZ framework.
 */

public class ZZTextView extends Frame implements ZZView {
public static final String rcsid = "$Id: ZZTextView.java,v 1.16.2.3 2001/08/16 13:50:01 bfallenstein Exp $";
    static final boolean dbg = false;
    static final void p(String s) { if(dbg) System.out.println(s); }
    static final void pa(String s) { System.out.println(s); }

    ZZCell windowCell;

    /** The cell we show (i.e., the cell currently accursed).
     *  If reraster is called, but the cell and its text haven't changed, we do
     *  nothing, so that the cursor position will not be screwed. (The text
     *  is not cached, instead the text in the TextArea component is used: this
     *  way, if the TextArea itself is used for editing, the text we find there
     *  will be the new text in the cell, so we will not screw the cursor
     *  position either.)
     *  <p>
     *  Note that we simply ignore updates when we have the focus.
     */
    ZZCell shown;

    /** Whether we're updating the content of the TextArea right now.
     *  When we're updating (i.e., write stuff from the structure into
     *  the text area), we obviously ignore events telling us the content
     *  of the text area has changed.
     */
    boolean isUpdating = false;

    /** Whether the text component currently has the focus. */
    boolean hasFocus;

    public ZZCell getViewcell() { return windowCell; }
    public void paintNow(float fract) {}

    TextArea txt = new TextArea("", 100, 100,
				TextArea.SCROLLBARS_VERTICAL_ONLY);

    public ZZTextView(ZZCell c) {
	windowCell = c;
	setLayout(new BorderLayout());
	add(txt, "Center");
	ZZUpdateManager.addView(this);
	txt.addTextListener(new TextListener() {
		public void textValueChanged(TextEvent e) {
		    if(isUpdating) return;
		    shown.setText(txt.getText());
		    ZZCursorReal.setOffs(windowCell, txt.getCaretPosition());
		}
	});
	txt.addFocusListener(new FocusListener() {
		public void focusGained(FocusEvent e) { hasFocus = true; }
		public void focusLost(FocusEvent e) { hasFocus = false; }
	});
	setBounds(0, 0, 200, 300);
	setVisible(true);
	reraster();
    }

    public boolean reraster() { 
	ZZCell accursed = ZZCursorReal.get(windowCell);
	if(!hasFocus && (!accursed.equals(shown) ||
			 !accursed.getText().equals(txt.getText()))) {
	    isUpdating = true;
	    txt.setText(accursed.getText());
	    int offs = ZZCursorReal.getOffs(windowCell);
	    if(offs == ZZCursorReal.NO_OFFSET) 
		txt.setCaretPosition(0);
	    else 
		txt.setCaretPosition(offs);
	    shown = accursed;
	    isUpdating = false;
	}
	return false;
    }
}

````



### Attachment: ZZTraverseCB.java _(1.3 KB)_
````
/*   
ZZSpace.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */

package org.gzigzag;
/** An interface for creating a ZZ space through traversal.
 * Cells are represented by their IDs.
 */

public interface ZZTraverseCB {
String rcsid = "$Id: ZZTraverseCB.java,v 1.6 2000/09/19 10:31:58 ajk Exp $";

	/** Start the traversal from the given home cell ID.
	 */
	void start(String home);
	/** Insert the new cell.
	 */
	void cell(String cur, String dim, int dir, String which,
		String content);
	/** Connect the two given cells. */
	void connect(String c1,String dim, int dir, String c2);
	/** That's all, folks. */
	void finish();
}

````



### Attachment: ZZUpdateManager.java _(7.1 KB)_
````
/*   
ZZUpdateManager.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** A single global instance to manage the updating of views.
 * The views are set in a priority order so that even if the user is
 * moving fast, he will get an immediate response through the less important
 * views not being updated at each step.
 */

public class ZZUpdateManager implements Runnable {
public static final String rcsid = "$Id: ZZUpdateManager.java,v 1.29 2001/02/27 08:36:15 raulir Exp $";
    public static boolean dbg = false;
    private static void p(String s) { if(dbg) ZZLogger.log(s); }
    private static void pa(String s) { ZZLogger.log(s); }

    /** The order of views, from the most important to the least.
     */
    private static Vector ordering = new Vector();

    /** Whether an update is currently in progress, through 
     * a view being painted. 
     */
    private static boolean updating;
    private static int disabled;
    private static boolean noanimation;
    /** Whether the currently ongoing update should stop immediately
     * and restart from the beginning
     */
    private static boolean restartUpd = false;

    public static void addView(ZZView v) { ordering.addElement(v); }
    public static void rmView(ZZView v) { ordering.removeElement(v); }

    /** Set the view that has the privilege of animating the next
     * update.
     * Setting this to null will make all views update fast.
     */
    public static void setFast(ZZView v) {
	p("Setfast: "+v + " cur: "+ordering.elementAt(0));
	if(v == null) {
	    noanimation = true;
	    return;
	}
	if(ordering.elementAt(0)!=v) {
	    ordering.removeElement(v);
	    ordering.insertElementAt(v, 0);
	}
    }


    /* Called by a space to inform that some cells have been 
     * changed 
     */
    public static void chg() {
	p("UPDMANAGER CHG");
	if(restartUpd) return;
	synchronized(ordering) {
		restartUpd = true;
		ordering.notifyAll();
	}
	p("UPDMANAGER CHGOUT");
    }

    /** Disable all updating of views.
     * XXX While frozen, might consider updating e.g. once every 
     * second...
     */
    public static void freeze() {
	p("ZZUpdatemanager freeze");
	synchronized(ordering) { disabled++; }
	p("ZZUpdatemanager frozen "+disabled);
    }
    /** Enable again the updating of views. */
    public static void thaw() {
	p("ZZUpdatemanager thaw");
	synchronized(ordering) {
	    if(disabled<=0)
		throw new ZZError("thaw() without matching freeze()!");
	    if(--disabled==0) ordering.notifyAll();
	}
	p("ZZUpdatemanager thawed "+disabled);
    }

    static ZZUpdateManager m = new ZZUpdateManager();
    static Thread t= new Thread(m);
    static {
	p("STARTORDTHREAD");
	t.start();
    }

    public void run() {
	try {
	int ind = -1;
	boolean reras = true;
	boolean anim = false;
	Vector curUpdVec = new Vector();

	while(true) {
	    p("STARTORD");
	    synchronized(ordering) {
		p("STARTORD SYNCHED");
		if(!anim) ind++;
		updating = false;
		try {
		while(disabled>0 || (ind>=curUpdVec.size() && !restartUpd)) {
		    p("STARTORD "+disabled+" "+ind+" "+restartUpd);
		    ordering.wait();
		}
		} catch(Exception e) {
		    ZZLogger.exc(e);
		}
		p("STARTORD WAITED");
		updating = true;
		if(restartUpd) {
		    restartUpd = false;
		    curUpdVec = (Vector)ordering.clone();
		    ind = 0;
		    reras = true;
		    // Try to make the system stop less at 
		    // inconvenient, unequal times.

		    // System.gc(); // doesn't seem to work.
		}
		if(curUpdVec.size()==0) continue;
	    }
	    try {
		p("STARTORD DOING " + ind + " "+ curUpdVec+" "+reras);
		ZZView v = (ZZView)curUpdVec.elementAt(ind);
		if(ind==0) { // animate if need be
		    if(reras) {
			timeNewCycle();

			anim = v.reraster();
			reras = false;
		    }
		    float fract = timeAnimFract();

		    if(fract >= 1 || !anim || noanimation) {
			fract = 1;
			anim = false;
			noanimation = false;
		    }
		    p("PN 0: "+fract+" "+anim+" "+lastStart+" "+millis);
		    // XXX paintNow() is not really safe here, because ZZ code
		    // in general isn't thread-safe. If Kaffe someday provides
		    // EventQueue.invokeAndWait(), this could be fixed.
		    boolean care = ZZDrawing.instance.enableQuality(false);
		    v.paintNow((float)fract);
		    if (fract == 1 && care) {
			ZZDrawing.instance.enableQuality(true);
			v.paintNow(1.0f);
		    }
		} else {
		    p("PN: "+ind);
		    v.reraster();
		    // XXX Ditto.
		    boolean care = ZZDrawing.instance.enableQuality(false);
		    v.paintNow(1.0f);
		    if (care) {
			ZZDrawing.instance.enableQuality(true);
			v.paintNow(1.0f);
		    }
		}
		((java.awt.Component)v).getToolkit().sync();
	    } catch(ZZError e) {
		ZZLogger.exc(e);
		System.out.println("EXCEPTION WHILE UPDATING!");
	    }
	    p("STARTORD DONE: anim "+anim);
	}
	} finally {
	    System.out.println("HELP! UPDATE LOOP STOPPED. XXX");
	}
    }

    static final long defmillis = 800;
    /** The time before the next user event
     * to try to be ready.
     */
    static final long trybefore = 150;
    /** The time to increment the interval with.
     */
    static final long inctime = 80;
    private static long lastStart = 0;
    /** The interval between start and end of animation.
     */
    private static long millis = defmillis;

    /** Called when we begin a new animation. */
    private void timeNewCycle() {
	long cur = System.currentTimeMillis();
	// Interval between start of last animation and start of the new one.
	long sinceLast = cur-lastStart;

	// sinceLast - millis = interval between end of last animation and
	// start of the new one. We try to end the last animation
	// trybefore ticks before the start of the new one, so if
	// sinceLast - millis < trybefore, the animation takes too long.
	if(sinceLast - millis < trybefore)
	    millis = sinceLast-trybefore; // Shorten the animation time.

	// If the animation didn't take too long, and if it's at least a unit
	// (inctime) shorter than it was by default, gradually lengthen it.
	else if(millis < defmillis - inctime)
	    millis += inctime;

	lastStart = cur;
    }

    private float timeAnimFract() {
	long cur = System.currentTimeMillis();

	double fract = 1.0;

	// If we are animating at all (20 milliseconds is
	// minimum time we try to use animation with), 
	// calculate the fraction of the animation we are at.
	if(millis > 20)
	    fract = (cur-lastStart) / (double)millis;

	// Test for a really weird JVM problem.
	if(cur - lastStart >= millis && fract < 1) {
	    System.out.println("AAAARRRRRGGGHHH!!! Division problem "+ cur + " "+lastStart+" "+millis);
	}

	return (float)fract;
    }

}



````



### Attachment: ZZView.java _(2.2 KB)_
````
/*   
ZZUpdateManager.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** A single view on the structure.
 * This class is mostly to work with ZZUpdateManager which tells these
 * classes to repaint themselves in response to changes in the structure
 * (expose events are separate and handled inside the classes themselves).
 * <p>
 * In event routines, passed instead of cells for update purposes
 * (asking ZZUpdateManager to make this view the fast-updated one).
 * Once ZZWindows are finished, should be replaced with ZZCell of
 * a ZZWindow.
 * <p>
 * Expect a parameter "complexity" to be added to reraster and paintNow
 * in the future in order for the ZZUpdateManager to be able to control
 * the frame rate.
 */
public interface ZZView {
String rcsid = "$Id: ZZView.java,v 1.18 2000/09/19 10:31:58 ajk Exp $";
    /** Called to enquire whether this view needs an update, given
     * that certain cells have been changed.
     * NOT YET USED
     */
    // public boolean needUpdate(ZZCell[] changed); 
	    // XXX dimensions of chgd cells!

    /** Recreate the view in memory (raster the cells etc).
     * @return true if it would be useful for the view to animate 
     * 		to the next view.
     */
    boolean reraster();
    /** Called to tell that this view should paint itself right now.
     * @param  fraction  The fraction between the old and the new views
     *			the animation should be at.
     */
    void paintNow(float fraction); 

    /** Get the cell in the structure representing this view.
     */
    ZZCell getViewcell();
}

````



### Attachment: ZZViewComponent.java _(6.8 KB)_
````
/*   
ZZViewComponent.java
 *    
 *    Copyright (c) 1999-2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.awt.event.*;
import java.awt.*;
import java.util.*;

/** A generic view as an AWT component.
 */
abstract public  class ZZViewComponent extends Panel implements ZZView, 
    MouseListener, MouseMotionListener {
public static final String rcsid = "$Id: ZZViewComponent.java,v 1.48.2.4 2002/02/10 12:39:20 bfallenstein Exp $";
    static public boolean dbg = false;
    private static void p(String s) { if(dbg) ZZLogger.log(s); }
    private static void pa(String s) { ZZLogger.log(s); }

    ZZCell viewCell;public ZZCell getViewcell() { return viewCell; }
    ZZKeyBindings kb;
    ZZView ctrlView, dataView;

    boolean needreraster = false;
    boolean validraster = false;

    ZZViewComponent parentView;

    Component pushedViewPanel;
    ZZViewComponent pushedView;

    /** ZZViewComponent per viewCell.
     */
    static Hashtable cpts = new Hashtable();

    static void redoCtrls(ZZCell vc) {
	if(vc == null) throw new ZZError("vc == null");
		
	if(vc.getRankLength("d.ctrlview") > 2)
	    throw new ZZError("d.ctrlview rank with more than two cells!");
	
	ZZCell cc, dc;
	if((cc = vc.s("d.ctrlview", -1)) != null)
	    dc = vc;
	else if((dc = vc.s("d.ctrlview", 1)) != null)
	    cc = vc;
	else
	    cc = (dc = vc);
	
	ZZViewComponent cv = (ZZViewComponent) cpts.get(cc);
	ZZViewComponent dv = (ZZViewComponent) cpts.get(dc);
	
	if(cv == null || dv == null)
	    // other ZZViewComponent doesn't exist yet
	    cv = (dv = (ZZViewComponent) cpts.get(vc));
	
	cv.setViewPair(dv, true);
	dv.setViewPair(cv, false);
	
/* // does somebody want it like this? -->
	ZZCell h = vc.h("d.ctrlview", -1);
	ZZViewComponent c = (ZZViewComponent)cpts.get(h);
	if(c != null) {
	    while((h=h.s("d.ctrlview", 1)) != null) {
		ZZViewComponent c1 = (ZZViewComponent)cpts.get(h);
		if(c1 != null)
		    c1.setCtrl(c);
	    }
	}
*/
    }

    public void setViewcell(ZZCell vc0) {
	viewCell = vc0;
	kb = new ZZKeyBindings1();
	cpts.put(vc0, this);
	redoCtrls(viewCell);
    }
    public void setViewPair(ZZView other, boolean ctrl) {
	if(ctrl) {
	    ctrlView = this;
	    dataView = other;
	} else {
	    ctrlView = other;
	    dataView = this;
	}
    }

    ZZViewComponent(ZZCell viewCell0) {
	this();
	setViewcell(viewCell0);
    }

    ZZViewComponent() {
	addFocusListener(new FocusListener() {
	public void focusGained(FocusEvent e) {
		p(this + " focusgained");
		repaint();
	 }
        public void focusLost(FocusEvent e) {
		p(this + " focuslost");
		repaint();
	 }
	});

	addMouseListener(this);
	addMouseMotionListener(this);

	addComponentListener(new ComponentAdapter() {
		public void componentResized(ComponentEvent e) {
			re_raster_soon();
		}
	});

	enableEvents(AWTEvent.KEY_EVENT_MASK);
    }

    public void addNotify() {
	ZZUpdateManager.addView(this);
        super.addNotify();
    }

    public void removeNotify() {
        ZZUpdateManager.rmView(this);
        super.removeNotify();
    } 

    protected void processEvent(AWTEvent e) {
	p("ProcessEvent: "+e);
	super.processEvent(e);
    }

    protected void processKeyEvent(KeyEvent e) {
	p("ProcessKeyEvent: "+e);
	
	// Apply any necessary key event hacks to this event.
	e = ZZKeyHacks.keyEventHack(e);
	p("After KeyEventHack: "+e);

        int id = e.getID();

	if(id == e.KEY_PRESSED) {
	    int kc = e.getKeyCode();
	    // These sometimes caused unshifted characters to
	    // appear. Very odd.
	    if(kc == e.VK_SHIFT || kc == e.VK_CONTROL || kc == e.VK_ALT 
		|| kc == e.VK_META) {
		super.processKeyEvent(e);
		return;
	    }
	    ZZUpdateManager.freeze();
	    try {
		//e.consume();
		if(kbd != null)
		    kb.perform(e, kbd.dataView, kbd.ctrlView, null);
		else
		    kb.perform(e, dataView, ctrlView, null);
		ZZObsTrigger.runObsQueue();
	    } finally { ZZUpdateManager.thaw(); }
	}
	// We don't let it go upstairs...
	// super.processKeyEvent(e);
    }


    public void mouseEntered(MouseEvent e)  {
       // XXX ??? 
       requestFocus();
    }
    public void mouseExited(MouseEvent e)  {
    }
    public void mousePressed(MouseEvent e) {
    }
    public void mouseReleased(MouseEvent e) {
    }
    public void mouseClicked(MouseEvent e)  {
	// System.out.println("MOUENT");
	// System.out.println(e);
	// kb.perform(k, ZZView.this);
	requestFocus();
	// System.out.println("MOURET");
	e.consume();
    }

    public void mouseDragged(MouseEvent e)  {
    }
    public void mouseMoved(MouseEvent e)  {
       // XXX ???     
       requestFocus();
    }

    public void destroy() {
	    ZZUpdateManager.rmView(this);
    }

    ZZViewComponent kbd;
    public void setKbdStandin(ZZViewComponent v) {
    	kbd = v;
    }
    public void re_raster_soon() {
	    // p(this + " RERASTERSOON");
	    needreraster = true;
	    repaint(50);
    }

    boolean wasInPaint;
    float fract;

    boolean dblbuf = true;
    private Image cache;
    private Dimension cacheSize;

    /** Paint this component into the given graphics object,
     * without consideration for double buffering.
     */
    public abstract void paintInto(Graphics gr);

    // Paint into the buffer and then into gr.
    public void paint(Graphics gr) {
	if(dblbuf) {
	    // XXX Really necessary every time?
	    Dimension d = getSize();
	    if(cache == null ||
		cacheSize == null ||
	       !cacheSize.equals(d)) {
		cacheSize = d;
		p("Creating cache: "+d.width+" "+d.height);
		cache=null;
		if(d.width>0&&d.height>0)
		    cache = createImage(d.width, d.height);
	    }
	    if(cache == null) {
		paintInto(gr);
	    } else {
		try {
		    Graphics g = cache.getGraphics();
		    paintInto(g);
		    // g.dispose() ???
		    gr.drawImage(cache, 0, 0, null);
		    // Dispose this as well?
		} catch(Throwable t) {
		    // FIXME ARGH!
		    cache = null;
		    paintInto(gr);
		}
	    }
	} else {
	    // Single-buffer. Flashes.
	    paintInto(gr);
	}
    }
    public void update(Graphics gr) { paint(gr); }

    public void paintNow(float fract) {
	wasInPaint = false;
	this.fract = fract;
	// p("Paintnow "+this+" "+parentView+" "+reraster+" "+anim);

        Graphics gr = getGraphics();
        if (gr == null) {
            repaint(30);
            return;
        }
	paint(gr);
    }

}




````



### Attachment: ZZWindows.java _(6.9 KB)_
````
/*   
ZZWindows.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka, killing by Antti-Juhani Kaijanaho,
 * triggering and rootwin support by Rauli Ruohonen
 */

package org.gzigzag;
import java.awt.*;
import java.awt.event.*;
import java.util.*;

public class ZZWindows {
public static final String rcsid = "$Id: ZZWindows.java,v 1.23 2001/01/03 16:47:50 raulir Exp $";
    public static boolean dbg = false;
    private static void p(String s) { if(dbg) ZZLogger.log(s); }
    private static void pa(String s) { ZZLogger.log(s); }

    /** Iff null, creates Frames at top level. */
    private static Container rootwin;
    private static ZZSpace rspace;
    private static Hashtable views, frames, ex;
    private static ZZObs obs = new ZZObs() { public void chg() { update(); }};

    /** Must be called before anything else. */
    public static void init(ZZSpace s,Container rootWin) {
	rootwin=rootWin;
	rspace=s;
	if(views!=null) updateEnd();
	views=new Hashtable();
	frames=new Hashtable();
	ex=new Hashtable();
	ZZObsTrigger.chg(obs);
    }
    public static synchronized void update() {
	p("update() start");
	ZZCell rcell=startCell();
	if(rcell==null) throw new ZZError("No 'Windows' cell found!");
	ZZCell s=rcell.getOrNewCell("d.1",1,obs);
	if(rootwin!=null) updateRoot(s);
	else updateFrames(s);
	updateEnd();
	p("update() end");
    }

    // XXX Should create a ZZWindow class for operating on the structure?
    public static Rectangle getBounds(ZZCell c, ZZObs obs) {
	try {
	    int[] a=ZZUtil.getInts(c.s("d.1",-1),"d.bounds",false,4,4,obs);
	    return new Rectangle(a[0], a[1], a[2], a[3]);
	} catch(ZZError e) {
	    return null;
	}
    }
    public static Rectangle getBounds(ZZCell c) { return getBounds(c,null); }
    public static void setBounds(ZZCell c, Rectangle r) {
	Rectangle b=getBounds(c);
	if(b!=null&&b.equals(r)) return;
	ZZUtil.putInts(c.s("d.1",-1), "d.bounds", false, 
		       new int[] { r.x, r.y, r.width, r.height });
    }
    public static ZZCell startCell() {
	return ZZDefaultSpace.findOnClientlist(rspace, "Windows", false);
    }
    public static synchronized ZZViewComponent getContent(ZZCell c) {
	String txt = c.getText(obs);
	if(txt.equals("Canvas")) {
	    ZZCanvasView v;
	    if(views.get(c) instanceof ZZCanvasView)
		v = (ZZCanvasView) views.get(c);
	    else 
		views.put(c, v = new ZZCanvasView());
	    ZZCell vcell = c.s("d.1", 1,obs);
	    if(vcell == null) return null;
	    v.setViewcell(vcell);
	    return v;
	}
	return null;
    }

    private static void updateRoot(ZZCell s) {
	ScalableFont.fmComp=rootwin;
	updateWindowAttributes(s,rootwin);
	updatePanels(s.s("d.2",1,obs),rootwin);
	rootwin.validate();
    }
    private static void updateFrames(ZZCell s) {
	s=s.s("d.2",1,obs);
	while(s!=null) {
	    boolean created=false;
	    ZZCell c=s.s("d.1",1,obs);
	    if(c!=null) {
		Frame f=(Frame)frames.get(c);
		if(f==null) {
		    created=true;
		    frames.put(c,f=new Frame());
		    initWindow(c,f);
		    final ZZCell cell=c;
		    f.addWindowListener(new WindowAdapter() {
			    public void windowClosing(WindowEvent e) {
				p("windowClosing()");
				ZZUpdateManager.freeze();
				try {
				    cell.s("d.1",-1).excise("d.2");
				    ZZObsTrigger.runObsQueue();
				} finally { ZZUpdateManager.thaw(); }
			    }
			});
		}
		ScalableFont.fmComp=f;
		ex.put(c,c);
		Rectangle r=getBounds(c,obs);
		if(r!=null&&!f.getBounds().equals(r)) f.setBounds(r);
		f.setTitle(s.getText(obs));
		p("Frame name: "+f.getTitle());
		Container cont=getContent(c);
		if(cont!=null) {
		    updateWindowAttributes(s,cont);
		    cont.removeAll(); // FIXME
		    updatePanels(c.s("d.2",1,obs),cont);
		    if(f.getComponentCount()!=1||f.getComponent(0)!=cont) {
			p("Changing frame component and validating.");
			f.removeAll();
			f.add(cont);
			f.validate();
		    }
		}
		if(created) f.setVisible(true);
	    }
	    s=s.s("d.2",1,obs);
	}
    }
    private static void updatePanels(ZZCell s,Container parent) {
	if(s==null) return;
	// FIXME This kludge is here so that applets still work. The real
	// functionality should be here Real Soon Now(TM). (Yeah, *right*)
	parent.removeAll();
	Container cont=getContent(s.s("d.1",1,obs));
	updateWindowAttributes(s,cont);
	parent.add(cont);
    }
    private static void initWindow(final ZZCell c,final Container w) {
	w.addComponentListener(new ComponentAdapter() {
		public void componentMoved(ComponentEvent e) {
		    ZZUpdateManager.freeze();
		    try {
			ZZObsTrigger.setEnabled(obs,false);
			setBounds(c, w.getBounds());
			ZZObsTrigger.setEnabled(obs,true);
			ZZObsTrigger.runObsQueue();
		    } finally { ZZUpdateManager.thaw(); }
		}
		public void componentResized(ComponentEvent e) {
		    ZZUpdateManager.freeze();
		    try {
			ZZObsTrigger.setEnabled(obs,false);
			setBounds(c, w.getBounds());
			ZZObsTrigger.setEnabled(obs,true);
			ZZObsTrigger.runObsQueue();
		    } finally { ZZUpdateManager.thaw(); }
		}
	    });
    }
    private static void updateWindowAttributes(ZZCell c,Container w) {
	ZZCell col=c.s("d.color",1,obs);
	if(col!=null) {
	    String colText = col.getText(obs);
	    
	    // See if it looks like an URL or a number.
	    if(Character.isDigit(colText.charAt(0)) ||
	       colText.charAt(0) == '-') 
		w.setBackground( Color.decode(colText) );
	    else {
		ZZLogger.log("Not digit first! '"+colText+"'");
		// XXX Find image, store it in the right place (should be 
		// in content...
		/*
		  URL url = null;
		  try {
		  url = new URL(cursor.h("d.photo", 1).getText());
		  } catch(MalformedURLException e) {
		  String s= e.toString();
		  g.drawString(s, 0, 0);
		  return;
		  }
		  if(!url.equals(cur)) {
		  cur = url;
		  img = getToolkit().getImage(url);
		  }
		  if(!g.drawImage(img, 0, 0, null)) {
		  repaint(1000);
		  }
		*/
	    }
	    
	    if((col=col.s("d.color", 1,obs)) != null) 
		w.setForeground( Color.decode(col.getText(obs)) );
	    }
    }
    private static void updateEnd() {
	for (Enumeration e = views.keys(); e.hasMoreElements();) {
	    ZZCell cell = (ZZCell) e.nextElement();
	    if(!ex.containsKey(cell)) views.remove(cell);
	}
	for (Enumeration e = frames.keys(); e.hasMoreElements();) {
	    ZZCell cell = (ZZCell) e.nextElement();
	    if(ex.containsKey(cell)) continue;
	    Frame f = (Frame)frames.get(cell);
	    f.dispose();
	    frames.remove(cell);
	}
	ex=new Hashtable();
    }
}

````

## Response:
I'd extract these in layers, starting with the headless core and leaving the AWT view code for last. Three of the uploaded files (`ZZPrimitiveActions.java`, `ZZPrimitiveCommand.zob`, `ZZUtil.java`) weren't in what I could see, so this covers the other 17. The `.zob` file only matters because `ZZPrimitiveCommand.java` is generated from it.

## What these files are

They're pieces of GZigZag, an implementation of Ted Nelson's ZigZag structure: cells connected along named dimensions. They fall into three layers:

| Layer | Files | Coupling |
|---|---|---|
| Observation | `ZZObs`, `ZZObsTrigger` | Light |
| Structure model | `ZZSpace`, `ZZRODimension`, `ZZSpacePart`, `ZZPath`, `ZZTraverseCB`, `ZZModule` | Moderate. They depend on `ZZCell`, `ZZDimension`, `ZZDimSpace` and others I haven't seen. |
| UI and views | `ZZView`, `ZZScene`, `ZZViewComponent`, `ZZPhotoView`, `ZZTextView`, `ZZWindows`, `ZZUpdateManager` | Heavy. AWT, global singletons, and classes like `ZZCursorReal`, `ZZKeyBindings`, `ZZCanvasView` and `ZZDrawing`. |

`ZZPrimitiveCommand` is generated code, so it follows whatever you do with the `.zob` preprocessor. `ZZSlicedDimSpace` is entirely commented out, so you can ignore it.

## Feasible projects, easiest first

**1. A dependency-tracking observer library (`ZZObs` and `ZZObsTrigger`)**
- This is the most self-contained piece, about 150 lines. Observers register against arbitrary objects. A change to an object queues the observers, and `runObsQueue()` fires each one once. The `Gob` linked-list trick gives fast re-registration.
- It has only two hard dependencies, `ZZLogger` and `ZZUpdateManager.chg()`. Replace the second with a listener hook and the library stands alone.
- Fixes to make while extracting:
  - `allTrigs` is a static `Vector` that holds every trigger forever, which is the memory leak the "XXX Store weak references" comment admits.
  - `chg(Object)` holds the instance lock, then takes the `obsQueue` lock, then calls `rmObs` on every other trigger. That lock ordering could deadlock.
  - The long comment on `runObsQueue` explains a workaround for JDK 1.1. `EventQueue.invokeLater` solves that problem today.

**2. A headless ZigZag structure library**
- Take `ZZSpace`, `ZZRODimension`, `ZZSpacePart`, `ZZPath`, `ZZTraverseCB` and the observer library, plus a small `Cell` interface. `ZZPath` only needs `s()`, `h()` and `findText()`, and its immutable `PathOp` chain converts neatly to lambdas.
- `ZZTraverseCB` is already a clean visitor for import and export, so file formats and serialization drop in easily.
- The catch is the transitive closure. These files pull in `ZZCell`, `ZZDimension`, `ZZDimSpace`, `ZZDefaultSpace`, `ZZCellHandle`, `Span`, `StringScroll`, `ZZConnection`, `ZZError` and `ZZLogger`, none of which I've seen. Sizing it is quick, though: copy the files into a fresh tree, compile, and let the missing symbols tell you the closure.
- `ZZModule` can come along if you replace the `Class.forName("org.gzigzag.module." + name).getField("module")` lookup with `java.util.ServiceLoader`.

**3. A new view layer (the hard one)**
- I'd extract only the ideas here: `ZZView` (reraster and paint), `ZZScene` (hit-testing and interpolated rendering) and the animation scheduling in `ZZUpdateManager`. Then reimplement them on Swing or JavaFX.
- `ZZUpdateManager` runs a static thread started from a static initializer, casts views to `java.awt.Component`, and calls `ZZDrawing.instance`. `ZZViewComponent` is tied to `ZZKeyBindings1`, `ZZKeyHacks` and a global `cpts` map. `ZZWindows` is built around `Frame`, plus an applet-era root-window workaround. Porting any of these is effectively a rewrite.
- I'd skip `ZZTextView` and `ZZPhotoView`. They're small, and a text panel and an image panel are quicker to write fresh.
- One bug is worth knowing about. In `ZZPhotoView`, the author says `drawString` "doesn't work". It does work, but `drawString(s, 0, 0)` puts the text baseline at y=0, so the text is drawn just above the visible area. Using the font's ascent as y fixes it.

## Recommendation

Start with project 1. It's a few hours of work, it's useful on its own, and it forces you to cut the global-singleton coupling that the rest of the code relies on. Then try project 2 using the compile-and-see approach to measure the real dependency closure. Treat project 3 as a separate rewrite, not an extraction.

If you upload the rest of the `org.gzigzag` package (especially `ZZCell`, `ZZDimension`, `ZZDimSpace` and `ZZDefaultSpace`), I can map the exact dependency closure for project 2.

## Prompt:
How would you modify your previous answer, given these files



### Attachment: ZZCellHandle.java _(2.6 KB)_
````
/*   
ZZCellHandle.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;

/** A ZigZag cell, as a handle.
 * This is a structure that is a handle to one cell.
 * All handles to the same cell should be equal to each other.
 * This means that the information contained within is only allowed
 * to depend on the cell ID.
 * <p>
 * The parts marked <b>EXPERIMENTAL</b> are such, and are subject to change.
 * Those parts are related to implementing virtual subparts of spaces.
 * The idea is to keep an Object handy that represents in a more simple
 * form what this cell actually <em>is</em> in that subpart.
 * Whether this is a speedup or a slowdown remains to be seen.
 */

public abstract class ZZCellHandle extends ZZCell {
public static final String rcsid = "$Id: ZZCellHandle.java,v 1.5 2001/02/23 08:33:37 ajk Exp $";

    /** The cell id.
     */
    public final String id;

    /** <b>EXPERIMENTAL:</b> the part of the space that this cell is in.
     */
    public final ZZSpacePart part;

    /** <b>EXPERIMENTAL:</b> the parsed ID (as provided by the space part)
     * of this cell.
     * This is supposed to be simply an easier-to-use representation
     * of the ID string for the spacepart's dimensions to use.
     * For instance, if the spacepart is a matrix, then parsedID could
     * be a java.awt.Point -like object that contains the coordinates
     * parsed out.
     */
    public final Object parsedID;

    public ZZCellHandle(String id, ZZSpacePart part, Object parsedID) {
        //if (id == null) throw new NullPointerException();
	this.id = id;
	this.part = part;
	this.parsedID = parsedID;
    }

    public String getID() {
	return id;
    }

    public boolean equals(Object o) {
	if(this == o) return true;
	if(!(o instanceof ZZCellHandle)) return false;
	ZZCellHandle it = (ZZCellHandle) o;
	return id == it.id || id.equals(it.id);
    }

    public int hashCode() {
	return id.hashCode();
    }
}


````



### Attachment: ZZCommand.java _(2.8 KB)_
````
/*   
ZZCommand.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Benjamin Fallenstein
 */

package org.gzigzag;
import java.awt.*;

/** An abstract class representing a command stored in zz space.
 * This should be thought of as a possible successor for ZZExec. Other than
 * ZZExec, the object created is not a scripting engine, but rather a
 * command which can be executed with a scripting engine. Subclasses of
 * ZZCommand are expected to implement ZOb.
 * <p>
 * This class also provides the static method getCommand, which returns the
 * ZZCommand associated with a cell, if any.
 */

public abstract class ZZCommand {
    /** Execute some code as a callback from the user interface.
     * This is a special execution context which is triggered through user
     * action on a user interface. Note that some of the params
     * are redundant and only provided for ease. All the other parameters
     * can be deduced from view, ctrlview and clicked.
     * @param view		View where command executed
     * @param cview		Control view of view where command executed
     * @param key		The key the user pressed, as string, if any
     * @param pt 		The point the user clicked on, if any
     * @param xi	The extra object - to get what was clicked, if any
     */
    public void execCallback(
		    ZZCell target,
		    ZZView view, 
		    ZZView cview,
		    String key,
		    Point pt, 
		    ZZScene xi
		     ) {
	exec(target);
    }

    // /** Execute with parameters.
    //  * XXX Needs rethinking of the arguments.
    //  */
    // public abstract void exec(ZZCell[] params);

    /** Execute with a single parameter.
     * An intermediate for calls which don't come from the UI, but from
     * somewhere else (e.g., a trigger).
     * <p>
     * Note that UI callbacks are proxied to exec by standard (that is, if
     * execCallback isn't overridden.)
     */
    public abstract void exec(ZZCell param);

    public static ZZCommand getCommand(ZZCell code) {
	// Check if it's a ZOb first:
	if(code.s("d.clone", -1) == null &&
	   code.s("d.1", 1) == null)
	    return null;
	ZOb z = ZZDefaultSpace.readZOb(code);
	if(z != null && z instanceof ZZCommand)
	    return (ZZCommand) z;
	return null;
    }
}

````



### Attachment: ZZConnection.java _(1.8 KB)_
````
/*   
ZZConnection.java
 *    
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuukka Hastrup
 */

package org.gzigzag;
/** A simple class defining a data type for connections in a ZZ space.
 *  Note, that nothing says a connection represented by a ZZConnection 
 *  object should exist. (You can test it with exists() method).
 *  @see org.gzigzag.ZZCell#getConns()
 */
public class ZZConnection {
	/** The start cell */
	public ZZCell c1;
	/** The dimension the connection goes along */
	public String dim;
	/** The direction of the connection */
	public int dir;
	/** The end cell */
	public ZZCell c2;
	public ZZConnection() {
	}
	/** Creates an object representing a link in ZZ space.
	 *  @param c1	The first cell
	 *  @param c2	The second cell
	 *  @param dim	The dimension of the connection
	 *  @param dir	The direction of the connection
	 */
	public ZZConnection(ZZCell c1, String dim, int dir, ZZCell c2) {
		this.c1 = c1;
		this.dim = dim;
		this.dir = dir;
		this.c2 = c2;
	}

	/** Tests whether this connection exists in it's space. */
	public boolean exists() {
		if(c1!=null && c2!=null && dim!=null && (dir==1||dir==-1)
		   && c1.s(dim, dir)==c2)
			return true;
		else
			return false;
			
	}
}


````



### Attachment: ZZCursor.java _(2.0 KB)_
````
/*   
ZZCursor.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** A thing that points to a cell or to an offset at a cell.
 * It is possible to have read-only ZZCursor objects which will
 * throw Errors for the modification attempts.
 */

public abstract class ZZCursor {
String rcsid = "$Id: ZZCursor.java,v 1.7 2000/11/25 00:36:33 tjl Exp $";
    /** Get the cell the cursor is pointing to. 
     */
    public abstract ZZCell get();
    /** Set the cursor to point to a cell.
     */
    public abstract void set(ZZCell c);
    /** Get the offset of this cursor.
     */
    public abstract int getOffs();
    /** Set the offset of this cursor.
     */
    public abstract void setOffs(int i);


    /** Set the cursor and offset to the given cursor.
     */
    public void set(ZZCursor c) {
	set(c.get());
	setOffs(c.getOffs());
    }

    /** The constant to specify that there is no offset 
     * for this cursor.
     */
    static public final int NO_OFFSET = -100;

    public boolean equals(Object o) {
	if(this == o) return true;
	if(!(o instanceof ZZCursor)) return false;
	ZZCursor oth = (ZZCursor) o;
	return (oth.get() == get() && oth.getOffs() == getOffs());
    }

    public String toString() {
	return "CURS: "+getOffs()+" of "+get()+"  Normal: "+super.toString();
    }

}

````



### Attachment: ZZCursorReal.java _(11.5 KB)_
````
/*   
ZZCursorReal.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** A real cursor in a structure.
 * This class also implements the commonly used
 * static methods for convenience.
 */

public class ZZCursorReal extends ZZCursor {
String rcsid = "$Id: ZZCursorReal.java,v 1.31.2.1 2002/02/10 12:37:40 bfallenstein Exp $";
    public static boolean dbg = false;
    static final void p(String s) { if(dbg) System.out.println(s); }
    static final void pa(String s) { System.out.println(s); }

    ZZCell ccell;
    public ZZCursorReal(ZZCell start) {
	// ccell = start.h("d.cursor-cargo", -1);
	// XXX ?? Which one is right?
	ccell = start;
    }
    public ZZCell get() { return get(ccell); }
    public void set(ZZCell c) { set(ccell, c); }
    public int getOffs() { return getOffs(ccell); }
    public void setOffs(int i) { setOffs(ccell, i); }

    /** Get the cell the given cursor cell or cargo cell is pointing to.
     */
    static public final ZZCell get(ZZCell start) {
	// XXX Maybe should be less allowing...
	return start.h("d.cursor-cargo", -1).
		h("d.cursor-list", -1).s("d.cursor", -1);
    }

    /** Set the given cursor cell to point to a cell.
     */
    static public void setcursor(ZZCell cur, ZZCell c) {
	removeFromCursorList(cur);
	if (c != null) addToCursorList(cur, c);
	trigger(cur);
    }

    /** Set the given cursor cargo to point to a cell.
     * If a cursor is cargoed already, use it. If no cursor is cargoed,
     * create one.
     */
    static public void setcargo(ZZCell cargo, ZZCell c) {
	if(cargo.s("d.cursor-cargo", -1) == null)
	    cargo.N("d.cursor-cargo", -1);
	setcursor(cargo.h("d.cursor-cargo", -1), c);
    }

    /** Set the given cursor cell or cursor cargo cell to point to a cell.
     * This routine has an interesting heuristic about creating
     * a cell on <code>d.cursor-cargo</code>: if 
     * the cell is already connected negwards on <code>d.cursor</code> or
     * <code>d.cursor-list</code>,
     * no cursor cargo cell is created, otherwise it is.
     * <p>
     * XXX should this be deprecated in favor of setcursor and setcargo?
     */
    static public final void set(ZZCell start, ZZCell c) {
	// A rather intricate check: if there's nothing on d.cursor-cargo,
	// create it but only if we're not going negwards on d.cursor or
	// d.cursor-list already.
	
	if(start.s("d.cursor-list", -1) == null &&
	   start.s("d.cursor", -1) == null) {
	    setcargo(start, c);
	} else
	    setcursor(start, c);
    }

    static public void set(ZZCell c, ZZCursor curs) {
	set(c, curs.get());
	setOffs(c, curs.getOffs());
    }

    /** Create a new cursor cell pointing to another cell.
     * Usually you use set to create a new cell, but sometimes you don't want
     * to attach a cargo cell on d.cursor-cargo; create just creates a new
     * cell on d.cursor and returns it.
     */
    static public final ZZCell create(ZZCell c) {
	ZZCell cur = c.N();
	addToCursorList(cur, c);
	return cur;
    }

    /** Attach a cursor to another one on d.cursor-cargo.
     * The first cell is removed from its current d.cursor-cargo rank and
     * inserted poswards behind the second one. Thus, the first cursor must
     * be a cursor cargo cell, not a real cursor cell (connected negwards 
     * along d.cursor).
     */
    static public final void attach(ZZCell which, ZZCell where) {
	if(which.s("d.cursor", -1) != null ||
	   which.s("d.cursor-list", -1) != null)
	    throw new ZZError("which is a real cursor cell");
	where.insert("d.cursor-cargo", 1, which);
	trigger(which);
    }

    /** Get the color associated with this cursor in the structure.
     */
    public java.awt.Color getColor() { return getColor(ccell); }

    /** Get the color associated with the given cursor in the structure.
     */
    static public final java.awt.Color getColor(ZZCell start) {
	ZZCell hc = start.h("d.cursor-cargo", -1);
	ZZCell col = hc.s("d.1", 1);
	if(col == null)
	    return null;
	try {
	    return new java.awt.Color(Integer.parseInt(col.getText()));
	} catch(NumberFormatException e) {
	    return null;
	}
    }

    /** Get the color associated with the given cursor, or white.
     * Return Color.white if no color is associated in the structure;
     * getColor would return null.
     */
    static public final java.awt.Color getColorOrWhite(ZZCell start) {
	java.awt.Color c = getColor(start);
	if(c == null) return java.awt.Color.white;
	return c;
    }
    
    /** Set the color associated with the given cursor in the
     * structure.
     * XXX Move cursor color to another dimension...
     */
    static public final void setColor(ZZCell start, java.awt.Color c) {
	ZZCell hc = start.h("d.cursor-cargo", -1);
	// if(hc.s("d.1", 1) != null)
	//     throw new Error("Can't set color of cursor: something's there.");
	hc.getOrNewCell("d.1",1).setText(String.valueOf(c.getRGB()));
    }

    /** Get the color of the first cursor associated with this cell.
     *  If there is no colored cursor accursing this cell, return null.
     */
    static public final java.awt.Color getAccursedColor(ZZCell c) {
	Enumeration e = ZZCursorReal.getPointers(c);
	while(e.hasMoreElements()) {
	    java.awt.Color col = ZZCursorReal.getColor((ZZCell)e.nextElement());
	    if(col != null) return col;
	}
	return null;
    }

    /** Set the offset of the given cursor.
     */
    static public void setOffs(ZZCell c, int i) {
	String s = null;
	if(i == NO_OFFSET)
	    s = "";
	else if(i < 0) {
	    throw new ZZError("Trying to set negative cursor offset!");
	} else
	    s = String.valueOf(i);
	c.h("d.cursor-cargo", -1).setText(s);
	trigger(c);
    }

    /** Get the offset of the given cursor.
     */
    static public int getOffs(ZZCell c) {
	String s = c.h("d.cursor-cargo").getText();
	if(s==null || s.equals("")) return NO_OFFSET;
	try {
	    int res = Integer.parseInt(s);
	    if(res < 0)  {
		ZZLogger.log(
		    "Serious: negative cursor offset. Resetting. "+c+" "+res);
		setOffs(c, NO_OFFSET);
		return NO_OFFSET;
	    }
	    return res;
	} catch(NumberFormatException e) {
	}
	return NO_OFFSET;
    }

    /** Delete extra cells associated only with the given cursor.
     * After this, deleting the cell will remove all traces.
     */
    static public void delete(ZZCell c) {
	if(c.s("d.cursor-cargo", 1) != null) return;
	c = c.s("d.cursor-cargo", -1);
	if(c.s("d.cursor-cargo", -1) != null) return;
	// Now, c is the cell on the cursor list with no other cargo,
	// and is not the original cell.
	removeFromCursorList(c);
	c.delete();
    }

    static class PointerEnum implements Enumeration {
            ZZCell c, cur;
	    { 
		p("PointerEnum created with " + c + ", cur = " + cur);
	    }
            
            public PointerEnum(ZZCell d) {
		c = d;
                cur = d.s("d.cursor", 1);
            }
            
            public boolean hasMoreElements() {
                boolean rv = cur != null;
                p("PointeEnum: hasMoreElements:" + rv);
                return rv;
            }

            public Object nextElement() {
                if (cur == null) throw new NoSuchElementException();
                Object rv = cur;
                cur = cur.s("d.cursor-list", 1);
                p("PointerEnum: rv = " + rv + ", cur = " + cur);
                return rv;
            }
    }

    /** Find cursors that point to the given cell.
     * This enumeration goes through the cells on the cursor list,
     * note that each of those may have cursor cargo attached with
     * them. There is not yet a function to go through the cursor
     * cargoes.
     */
    static public Enumeration getPointers(final ZZCell c) {
        return new PointerEnum(c);
    }
    
    /** Adjust the cursors on a cell after text insertion or deletion.
     * This in- or decrements cursors whose offsets are past a given
     * division point. Cursors without offsets remain unchanged.
     * @param acc The cell on which the cursors to be changed are.
     * @param div The index from which on we want offsets to be changed.
     * @param inc The amount by which we want offsets to be changed.
     *            Negative for deletions. Note that offsets won't be set
     *            below div, that is after we've deleted seven characters,
     *            a cursor which was on the third character will be set
     *            where the first char was, not (7-3=)four posns before that.
     */
    static public void adjustCursors(ZZCell acc, int div, int inc) {
	Enumeration e = getPointers(acc);
	while(e.hasMoreElements()) {
	    ZZCell curs = (ZZCell)e.nextElement();
	    int offs = getOffs(curs);
	    if(offs != NO_OFFSET && offs >= div) {
		if(offs + inc < div)
		    setOffs(curs, div);
		else
		    setOffs(curs, offs + inc);
	    }
	}
    }

    /** Find the visual text offset for the cursor.
     * This is purely a convenience routine: if the cursor has an
     * offset, it returns that, but if not, it returns half of the
     * length of text in the accursed cell.
     */
    static public int getVisualTextOffset(ZZCell c) {
	int ret = getOffs(c);
	if(ret == NO_OFFSET)
	    ret = get(c).getText().length() / 2;
	return ret;
    }

    // Private stuff

    static private void removeFromCursorList(ZZCell cur) {
	ZZCell acc = cur.s("d.cursor", -1);
	if(acc != null)
	    cur.disconnect("d.cursor", -1);
	
	ZZCell nb = cur.s("d.cursor-list", 1);
	if(acc != null && nb != null)
	    nb.connect("d.cursor", -1, acc);
		
	cur.excise("d.cursor-list");
    }

    static private void addToCursorList(ZZCell cur, ZZCell c) {
	ZZCell nb = c.s("d.cursor", 1);
	if(nb != null)
	    // insert instead of connect so that when we have headcells on
	    // looping ranks, d.cursor-list can loop. (Dunno if we need this,
	    // but kinda seemed right.)
	    nb.h("d.cursor-list", 1)
		.insert("d.cursor-list", 1, cur);
	else
	    c.connect("d.cursor", 1, cur);
    }

    static private LoopDetector trigdetect = null;
    static private boolean stoptrig = false;

    static private void trigger(ZZCell start) {
	p("Cursor trigger triggered");
	boolean wasnull = false;
	if(trigdetect == null) {
	    wasnull = true;
	    trigdetect = new LoopDetector();
	}
	
	synchronized(trigdetect) {
	try {
	    ZZCell c = start.h("d.cursor-cargo", -1);
	    for(; c != null; c = c.s("d.cursor-cargo", 1)) {
		if(c.s("d..cursor-trigger", -1) == null) continue;
		p(""+c);

		if(trigdetect.isLooping(c)) {
		    ZZLogger.log("Detected trigger loop while trying "+
				 "to set a cursor. Breaking triggering now.");
		    stoptrig = true;
		    break;
		}
		
		ZZCell commcell = c.h("d..cursor-trigger", -1);
		ZZCommand comm = ZZCommand.getCommand(commcell);
		if(comm != null) {
		    p("Calling trigger command: "+commcell.getText());
		    try {
			comm.exec(c);
		    } catch(ZZError e) {
			ZZLogger.exc(e, "Cursor trigger exception: ");
			stoptrig = true;
		    }
		    if(stoptrig) break;
		}
	    }
	} finally {
	    if(wasnull) {
		trigdetect = null;
		stoptrig = false;
	    }
	}
	}
    }
}

````



### Attachment: ZZCursorVirtual.java _(1.8 KB)_
````
/*   
ZZCursorVirtual.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** A virtual cursor.
 * Used by clang to optimize away some puts and gets, e.g. to postpone
 * setting the view cursor in the structure until the end of the routine.
 * XXX Clang definition needs to be VERY specific about what timings
 * are guaranteed in storing things to the structure.
 */
public class ZZCursorVirtual extends ZZCursor {
String rcsid = "$Id: ZZCursorVirtual.java,v 1.7 2000/11/25 00:36:33 tjl Exp $";
    ZZCell val;
    int offs;

    public ZZCursorVirtual(ZZCell startVal) {
	val = startVal;
	offs = NO_OFFSET;
    }
    public ZZCursorVirtual(ZZCell startVal, int startOffset) {
	val = startVal;
	offs = startOffset;
    }
    public ZZCursorVirtual(ZZCursor curs) {
	val = curs.get();
	offs = curs.getOffs();
    }

    static public ZZCursorVirtual createFromReal(ZZCell curs) {
	return new ZZCursorVirtual(ZZCursorReal.get(curs),
				    ZZCursorReal.getOffs(curs));
    }

    public ZZCell get() { return val; }
    public void set(ZZCell c) { val = c; }
    public int getOffs() { return offs; }
    public void setOffs(int i) { offs = i; }
}



````



### Attachment: ZZDimension.java _(5.0 KB)_
````
/*   
ZZDimension.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** Dimension-centric implementation.
 * A ZZDimension represents a single dimension of a space.
 * It is called with the cell objects that simply contai.
 * <p>
 * Some of the routines are given here so that they may be optimized.
 * The absolute core routines that every subclass must implement 
 * are the abstract routines <b>s, connect and disconnect</b>.
 */

public abstract class ZZDimension {
public static final String rcsid = "$Id: ZZDimension.java,v 1.25 2001/01/24 08:32:16 veparkki Exp $";

    /** The space this dimension is affiliated with. */
    protected ZZDimSpace space;
    public void setSpace(ZZDimSpace s) { space = s; }

    /** The observer trigger for this dimension.
     */
    protected ZZObsTrigger triggers = new ZZObsTrigger();

    // These three routines need to be implemented

    /** Get another cell <I>steps</I> steps on the dimension from c.
     * @param c     The cell
     * @param steps Number of steps, can be negative.
     */
    public abstract ZZCellHandle s(ZZCellHandle c, int steps, ZZObs o); 
    /** Connect the two cells in this dimension, in order.
     */
    public abstract void connect(ZZCellHandle c, ZZCellHandle d);
    /** Disconnect the cell in the given direction.
     */
    public abstract void disconnect(ZZCellHandle c, int dir);

    // Really throw out the old functions and 
    // make them so that no-one can override them.

/*
    final public String s(String c, int steps, ZZObs o) 
	{ throw new ZZError("Old dim API"); } 
    final public void connect(String c, String d)
	{ throw new ZZError("Old dim API"); } 
    final public void disconnect(String c, int dir)
	{ throw new ZZError("Old dim API"); } 
 */


    /** The rest of the operations from here can be overridden
     * for optimizations, but do it is not required: the above operations
     * are all that is really needed.
     */

    /** Get headcell.
     */

    // XXX loops
    public ZZCellHandle h(ZZCellHandle c, int dir, ZZObs o) {
	ZZCellHandle orig = c;
	ZZCellHandle prev = c;
	while((c=s(c, dir, o))!=null) {
		prev = c;
		// Return lexically maximum id.
		if(c.equals(orig)) {
		    // throw new ZZInfiniteLoop("CIRCULAR HEAD");
		    ZZCellHandle lid = c;
		    while((c=s(c ,dir, o))!=null
			&& !c.equals(orig)) {
			if(c.id.compareTo(lid.id) > 0) lid = c;
		    }
		    return lid;
		}
	}
	return prev;
    }

    public ZZCellHandle h(ZZCellHandle c, int dir) {
	return h(c, dir, null);
    }

    final void connect(ZZCellHandle c, int dir, ZZCellHandle d) {
	    if(dir<0) 
		    connect(d,c);
	    else
		    connect(c,d);
    }

    public void insert(ZZCellHandle c, int dir, ZZCellHandle d) {
	    ZZCellHandle p = s(d, 1);
	    ZZCellHandle m = s(d, -1);
	    //System.out.println("c = " + c);
	    //System.out.println("d = " + d);
	    //System.out.println("p = " + p);
	    //System.out.println("m = " + m);

	    if(p!=null)
		disconnect(p, -1);
	    if(m!=null)
		disconnect(m, 1);
	    if(p!=null && m!=null)
		connect(m, p);
	    ZZCellHandle o = s(c, dir);
	    if(o!=null)
		disconnect(c, dir);
	    
	    connect(c,dir,d);
	    if(o!=null)
		connect(d,dir,o);
    }

    /** Remove the given cell from this dimension.
     */
    public void excise(ZZCellHandle c) {
	    ZZCellHandle p = s(c, 1);
	    ZZCellHandle m = s(c, -1);
	    disconnect(c, 1);
	    disconnect(c, -1);
	    if(p!=null && m!=null)
		    connect(m, p);
    }

    public void hop(ZZCellHandle c, int steps) {
	if(steps == 0) return;
	ZZCellHandle n = s(c, steps);
	if(n == null ) return;
	insert(n, (steps > 0 ? 1 : -1), c);
    }

    /** Find the text in a cell. 
     * This routine is here so that it may be optimized if desired.
     * If it is, then the main space object must remember to update 
     * this dimension if it keeps a cache in a hash etc.
     */
    public ZZCellHandle findText(ZZCellHandle c, int dir, String txt) {
	    ZZCellHandle cur = s(c, 1);
	    while(cur != null && cur != c && 
		!cur.getText().equals(txt))
		    cur = s(cur, 1);
	    if(cur==c) return null;
	    return cur;
    }

    public ZZCellHandle s(ZZCellHandle c, int steps) {
	return s(c, steps, null);
    }

    // Same goes for these, obviously
    // ZZCell intersect(ZZCell c, int dir, ZZDimension d2, ZZCell c2, int dir2);
    // ZZCell[] intersectAll(ZZCell c, int dir, ZZDimension d2, ZZCell c2, int dir2);




}

````



### Attachment: ZZDimSpace.java _(12.3 KB)_
````
/*   
ZZDimSpace.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka (ID-stuff and d.cellcreation by Tuukka Hastrup)
 */
package org.gzigzag;
import java.util.*;

/** A dimension-centric implementation of a space.
 * The internals of this implementation are done by dimension objects
 * which know how cells are connected in their dimension.
 * @see ZZDimension
 */

public class ZZDimSpace extends ZZSpace {
public static final String rcsid = "$Id: ZZDimSpace.java,v 1.49 2001/03/07 12:51:24 ajk Exp $";

// XXX These should be made garbage collectable ASAP!

	/** ZZDimension given string.  */
	Hashtable dims = new Hashtable();

	/** DimCell given id.  */
	Hashtable cells = new Hashtable();

	/** Space parts by names. */
	Hashtable spaceParts = new Hashtable();

	/** Contents by id. */
        Hashtable contents = new Hashtable();

	/** Cell by span. 
	 * If this is null, overlapping spans cannot be searched.
	 */
	SpanSet spanset = null;
    
    public ZZDimSpace() { this(false); }
    public ZZDimSpace(boolean readonly) {
        super(readonly);
    }

	/** Obtain the space part corresponding to the given ID.
	 */
	public ZZSpacePart getSpacePartByID(String id) {
	    return (ZZSpacePart)spaceParts.get(id);
	}

	/** Obtain the ZZDimension corresponding to the given string.
	 */
	final public ZZDimension d(String s) { 
		ZZDimension r = (ZZDimension)dims.get(s); 
		if(r==null) {
		    r = createDimension(s);
		    if(r == null) 
			throw new ZZError("Illegal dimension: '"+s+"'");
		    dims.put(s,r);
		    if (!readonly) updateMasterDimList(s);
		}
		return r;
	}

	/** The cell given by the identifier, <b>if already created</b>.
	 * Note that this routine only returns existing cells,
	 * i.e. objects that have already been created.
	 * Dormant cells or virtual cells need to be obtained through
	 * getCellByID.
	 */
	DimCell c(String id) { return (DimCell)cells.get(id); }

	/** Obtain the cell given by the identifier.
	 */
	public ZZCell getCellByID(String s) {
            int at = s.indexOf('@');
            if (at != -1 && getIDOrNull() != null && s.substring(at+1).equals(getID())) {
                s = s.substring(0, at);
                at = -1;
            }
	    int ind = s.indexOf(':');
            if (at == -1 && ind == -1) {
                try {
                    if (nextID != null) {
                        long cid = Long.parseLong(s);
                        long nid = Long.parseLong(nextID);
                        if (cid >= nid) setNextID("" + (cid+1));
                    }
                } catch(NumberFormatException e) {
                    return null;
                }
            }
	    if(ind != -1) {
		ZZSpacePart part = getSpacePartByID(s.substring(0, ind));
		if(part == null) 
		    throw new ZZError("No such part for cell "+s);
		return getCellByID(part, s.substring(ind+1));
	    } 
	    return getCellByID(null, s);
	}
    
	/** Obtain a cell, possibly in a space part.
	 */
	public DimCell getCellByID(ZZSpacePart p, String s0) {
	    String s = (p != null ? p.id + ":" + s0 : s0);
            DimCell ret = null;
            if (p != null) ret = p.getCellByID(s0);
	    if (ret == null) ret = (DimCell) cells.get(s);
	    if(ret==null) {
		DimCell d = new DimCell(s, p, 
				    (p != null ? p.parseIDPart(s0) : null));
		cells.put(d.id, d);
		ret = d;
	    }
	    return ret;
	}

	public DimCell getCellByID(ZZSpacePart p, String s0, Object o) {
	    String s = p.id + ":" + s0;
            DimCell ret = null;
            if (p != null) ret = p.getCellByID(s0);
	    if (ret == null) ret =  (DimCell) cells.get(s);
	    if(ret==null) {
		DimCell d = new DimCell(s, p, o);
		cells.put(d.id, d);
		ret = d;
	    }
	    return ret;
	}
	
	public ZZCell[] overlaps(Span sp) {
	    if(spanset == null) return null;
	    Object[] o = spanset.overlaps(sp);
	    ZZCell[] res = new ZZCell[o.length];
	    for(int i=0; i<o.length; i++) res[i] = c((String)o[i]);
	    return res;
	}

	ZZObsTrigger textTrig = new ZZObsTrigger();

	public void invalidateText(String id) {
            DimCell dc = c(id);
            if (dc == null) {
                ZZLogger.log("FIXME: invalidateText called with a nonexistent ID!");
                return;
            }
	    // Do nothing now. Maybe?
	}

	protected Span getSpan(String id) {
	    return (Span) contents.get(id);
	}
	protected String getText(String id) {
	    String s = (String) contents.get(id);
	    return s;
	}
        protected void setText(String id, Object ct) {
	    contents.put(id,ct);
	    if(spanset != null && ct instanceof Span)
		spanset.addSpan((Span)ct, id);
	    // XXX what if a span content is replaced by a non-span content?!?
	    // -- for now we can assume span contents don't change (I know
	    // no span-using code that does) but later, we'll need that?
	}

	/** A ZZCell in the dimspace representation.
	 * Interestingly, in this representation the cell is simply
	 * its identifier and the implicit reference to the surrounding
	 * ZZDimSpace object.
	 * <p>
	 * The reason for this is that it needs to be allowable for
	 * two cell objects with the same ID to be created without
	 * too much confusion.
	 * <p>
	 * This is because we're aiming for Java 1.1 which does not 
	 * have weak references.
	 */
	public class DimCell extends ZZCellHandle {

		protected DimCell(String id) {
		    super(id, null, null);
		}
            protected DimCell(ZZSpacePart part, Object parsedID) {
                this(part.generateID(parsedID), part, parsedID);
            }

		protected DimCell(String id, ZZSpacePart p, Object o) {
		    super(id, p, o);
		}

		public String[] getRankNames() { 
			throw new ZZError("getRankNames Not implemented");
		}

		public final ZZSpace getSpace() { return ZZDimSpace.this; }

		public void connect(String dim, ZZCell to) {
                    this.disconnect(dim, 1);
                    to.disconnect(dim, -1);
			d(dim).connect(this, ((DimCell)to));
		}
		public void disconnect(String dim, int dir) {
			d(dim).disconnect(this, dir);
		}
		public void insert(String dim, int dir, ZZCell to) {
			d(dim).insert(this, dir, ((DimCell)to));
		}
		public void hop(String dim, int steps) {
		    d(dim).hop(this, steps);
		}

		public ZZCell s(String dim, int dir, ZZObs o) {
			return d(dim).s(this, dir, o);
		}

		public ZZCell N(String dim, int dir, ZZObs o, long flags)
		{
		synchronized(ZZDimSpace.this) {
			DimCell n = getNewCell(id);
			insert(dim, dir, n);
			if(o != null)
			    d(dim).s(this, dir, o);
			return n;
		}
		}

		public ZZCell N() {
		synchronized(ZZDimSpace.this) {
		    return getNewCell(id);
		}
		}

		public void setText(String text) {
		synchronized(ZZDimSpace.this) {
			ZZCell rootClone = getRootclone();
			if(rootClone != this) {
			    rootClone.setText(text);
			    return;
			}
			if(part != null) {
			    part.setContent(this, text);
			} else {
			    p("TEXT");
			    ZZDimSpace.this.setText(id, text);
			    textTrig.chg(id);
			}
		}
		}
		public void setSpan(Span text) {
		synchronized(ZZDimSpace.this) {
			ZZCell rootClone = getRootclone();
			if(rootClone != this) {
			    rootClone.setSpan(text);
			    return;
			}
			if(part != null) {
			    part.setContent(this, text);
			} else {
			    ZZDimSpace.this.setText(id, text);
			    textTrig.chg(id);
			}
		}
		}

		// XXX part.getText should NOT BE HERE!!!!
		public String getText(ZZObs o) {
		synchronized(ZZDimSpace.this) {
		    String s;
		    // XXX Interaction with slices??
		    // XXX Interaction with ZZObs
			ZZCell rootClone = getRootclone();
			if(rootClone != this)
			    return rootClone.getText(o);
			if(o != null) textTrig.addObs(id, o);
			if(part != null)
			    s = part.getText(this);
			else
			    s = ZZDimSpace.this.getText(id);
			if( s == null )
			    return "";
			return s;
		}
		}
		public Span getSpan(ZZObs o) {
		synchronized(ZZDimSpace.this) {
		    ZZCell rootClone = getRootclone();
		// XXX As in getText!!!
		    if(rootClone != this)
			return rootClone.getSpan(o);
		    if(o != null) textTrig.addObs(id, o);
		    if(part != null)
			return part.getSpan(this);
		    return ZZDimSpace.this.getSpan(id);
		}
		}

		public boolean equals(ZZCell c) {
		    DimCell o = (DimCell)c;
		    return (this == o) ||
			(ZZDimSpace.this == o.getSpace() &&
			    id.equals(o.id));
		}

		public void delete() {
		synchronized(ZZDimSpace.this) {
			ZZDimSpace.this.deleteCell(this);
		}
		}
		
		public ZZCell h(String dim, int dir, 
			boolean ensuremove, ZZObs o) {
		    ZZCell res = d(dim).h(this, dir, o);
		    if(ensuremove && (res == this)) return null;
		    return res;
		}

	}

	void deleteCell(ZZCell c) { 
	    for(Enumeration e = dims.keys(); e.hasMoreElements(); ) {
		((ZZDimension)(dims.get(e.nextElement()))).excise((DimCell)c);
	    }
	}

        String nextID="2"; // first cell is home cell, ID 1
    protected void setNextID(String s) {
        nextID = s;
    }

	/** Get the cell ID relative to a given ID, in creation order.
	 *  @param id		Given ID
	 *  @param steps	How many steps to take (negative means earlier)
	 */
        public String getRelativeCellID(String id, int steps) {
                try {
                        long i = Long.parseLong(id);
                        if(i<0 || i+steps<1)
                                return null;
                        return ""+(i+steps);
                } catch(NumberFormatException e) {
                        return null;
                }
        }
        protected String getFreeCellID() {
                String curID = nextID;
                setNextID(getRelativeCellID(nextID, 1));
                return curID;
        }

        // XXX What's this? (compared to the next)
        protected DimCell getNewCell(String id) {
                return getNewCell();
        }
        protected DimCell getNewCell() {
                return (DimCell)getCellByID(nextID);
        }
	public ZZCell newCell() {
		return getNewCell();
	}

	/** A simple dimension listing the cells in creation order.
	 *  It uses getRelativeCellID() to find the cells, and will check
	 *  nextID to know whether the cell doesn't exist yet.
	 *  XXX The positive steps taken must be 1 or skipping nextID 
	 *  is possible!
         */
        class IDDimension extends ZZRODimension {
		/** get a cell ID along the dimension.
		 * XXX Obs doesn't work correctly.
                 */
                public ZZCellHandle s(ZZCellHandle c, int steps, ZZObs o) {
                        String id = getRelativeCellID(c.id, steps);
                        if(id == null || id.equals(nextID))
                                return null;
                        return (DimCell)getCellByID(id);
                }
        }



	// XXX posConnections()?
	public ZZCell[] findLongRankHeads(String dim) { return null; }

	public void rmAllObs(ZZObs o) { }

	public String getHomeCellID() { 
	    return "1";
	}
	public ZZCell getHomeCell() { 
	    return getCellByID(getHomeCellID());
	}

	/** Create a new dimension with the name s.
	 * In order to make things fast, this is the method
	 * to override instead of the d() method (which is final
	 * exactly because of that).
	 * <p>
	 * The default version simply returns a new ZZLocalDimension,
	 * except for d.cellcreation
	 * <p>
	 * Note that this routine should NOT touch the dimension hash
	 * but simply return the new dimension.
	 */
	protected ZZDimension createDimension(String s) {
	    if(s.indexOf(':') != -1) return createPartDimension(s);
		if(!validDim(s)) return null;
		ZZDimension l;
		if(s.equals("d.cellcreation")) {
			l = new IDDimension();
		} else {
			l = new ZZLocalDimension();
		}
		l.setSpace(this);
		return l;

	}

	protected ZZDimension createPartDimension(String s) {
	    int ind = s.indexOf(':');
	    ZZSpacePart part = getSpacePartByID(s.substring(0, ind));
	    ZZDimension d = part.getDim(s.substring(ind+1));
	    d.setSpace(this);
	    return d;
	}


}


````



### Attachment: ZZDrawing.java _(3.3 KB)_
````
/*   
ZZDrawing.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.awt.*;

/** An abstraction of improved drawing primitives.
 * We are aiming for Java 1.1, but for instance Java2D provides
 * many features we'd like to use, if present.
 * Normally, simply testing <pre>g instanceof Graphics2D</pre>
 * would be sufficient but we want to also be able to <em>compile</em>
 * with only the 1.1 libraries available, so we cannot do that.
 * Also, we want to be able to hook up to e.g. OpenGL without 
 * having to create a full Java2D implementation there.
 * <p>
 * This class is used to abstract out any graphics operations that
 * are not in java.awt.Graphics. The default of this class is that
 * each operation is a no-op (unless otherwise specified).
 * All code should function reasonably under such an assumption.
 * Subclasses of this object are allowed to implement operations
 * in any way they like.
 * <p>
 * TODO: Should make it possible to get drawing parameters
 * from either system
 * properties (possibly preferable) or the ZZ structure.
 */

public class ZZDrawing {
public static final String rcsid = "$Id: ZZDrawing.java,v 1.6 2001/03/26 12:41:00 tjl Exp $";

    /** Get a human-readable string identifying the ZZDrawing
     * instance and the settings.
     */
    public String getType() {
	return "Default 1.1 API -compliant version: no antialiasing or rotation";
    }

    /** The default instance of ZZDrawing for others to use.
     */
    static public final ZZDrawing instance = createInstance();
    private boolean qEnabled = true;

    /** Create an instance.
     */
    static public ZZDrawing createInstance() {
	ZZDrawing ret = null;
	Class g2d = null, zzdj2d = null;
	try {
	    g2d = Class.forName("java.awt.Graphics2D");
	    zzdj2d = Class.forName("org.gzigzag.ZZDrawingJ2D");
	    ret = (ZZDrawing)zzdj2d.newInstance();
	} catch(Exception e) {
	    ZZLogger.exc(e);
	    if(g2d != null) {
		ZZLogger.log("Graphics2D found but support not compiled in.");
	    }
	}
	if(ret == null) ret = new ZZDrawing();
	return ret;
    }

    /** Set rendering so that the graphics context will draw
     * over translucently, with the given alpha.
     */
    public void setAlpha(Graphics g, float alpha) {
    }

    /** Set good rendering quality.
     * XXX Should take a parameter.
     */
    public void setQuality(Graphics g) {
    }

    /** Return true if it makes any difference. */
    public boolean enableQuality(boolean t) {
	qEnabled = t;
	return false;
    }
    public boolean qualityEnabled() { return qEnabled; }

    /** Set the defaults. To be called on all
     * Graphics objects used.
     */
    public void setDefaults(Graphics g0) {
    }
}


````



### Attachment: ZZEvObs.java _(1.1 KB)_
````
/*   
ZZEvObs.java
 *    
 *    Copyright (c) 1999, Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */

package org.gzigzag;
/** A simple class that observes a cell.
 * Note that this class is to be used only for one cell: the two calls
 *   chg(1) chg(2) can be replaced with chg(2). There will in the future be
 * a new class, ZZMultiCellObs that gets a ZZCell[] as its parameter.
 */

public interface ZZEvObs {
String rcsid = "$Id: ZZEvObs.java,v 1.5 2000/09/19 10:31:58 ajk Exp $";
	/** Called when something is changed.
	 */

	void chg();
}



````



### Attachment: ZZExec.java _(2.1 KB)_
````
/*   
ZZExec.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.awt.*;

/** A generic script engine interface.
 * ZZExec specifies a way of interfacing various script engines to the ZZ space.
 * At the moment, only UI callback functions are allowed - later, it will be
 * expanded to a more complete class.
 */

public interface ZZExec {
String rcsid = "$Id: ZZExec.java,v 1.12 2000/09/19 10:31:58 ajk Exp $";
    /** Execute some code as a callback from the user interface.
     * This is a special execution context which is triggered through user
     * action on an user interface. Note that some of the params
     * are redundant and only provided for ease. All the other parameters
     * can be deduced from code, view, ctrlview and clicked.
     * @param code		Cell to start execution from
     * @param view		View where command executed
     * @param cview		Control view of view where command executed
     * @param key	The key the user pressed, as string, if any
     * @param pt 	The point the user clicked on, if any
     * @param xi    The extra object - to get what was clicked, if any
     */
    void execCallback(ZZCell code, 
		    ZZCell target,
		    ZZView view, 
		    ZZView cview,
		    String key,
		    Point pt, 
		    ZZScene xi
		     );
    // /** Execute some code with parameters.
    //  * XXX Needs rethinking of the arguments.
    //  */
    // public void exec(ZZCell code, ZZCell[] params);
}

````



### Attachment: ZZIter.java _(4.0 KB)_
````
/*   
ZZIter.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */

package org.gzigzag;
import java.awt.*;
import java.awt.datatransfer.*;
import java.util.*;

/** Help for iterating along ranks in various ways.
 */

public class ZZIter {
public static final String rcsid = "$Id: ZZIter.java,v 1.3 2000/11/01 00:39:06 tjl Exp $";
    public static final boolean dbg = false;
    static final void p(String s) { if(dbg) System.out.println(s); }

    /** An callback interface for iterating along a rank with
     * the cell number.
     */
    public interface NIter {
	/** Do whatever you like with this cell, which is the nth from
	 * wherever we began.
	 * @return True, if the iteration is to continue (in this direction).
	 */
	boolean go(ZZCell c, int nth);
    }

    /** Go along a rank, starting from a cell, interleaving alternate
     * directions.
     * @param c The cell to start from.
     * @param included Whether the first cell is also included.
     * @param d The dimension to go along.
     * @param fdir The direction to take the first step in.
     * @param iter The callback object.
     */
    public static void alternate(ZZCell c, boolean included,
		String d, int fdir, NIter iter) {
	if(c == null) return;
	int i = 0;
	if(included) 
	    if(!iter.go(c, 0)) return;
	boolean in = true;
	boolean op = true;
	ZZCell inc = c;
	ZZCell opc = c;
	while(in || op) {
	    i++;
	    if(in) {
		inc = inc.s(d, fdir);
		if(inc == null) 
		    in = false;
		else 
		    if(!iter.go(inc, fdir * i))
			in = false;
	    }
	    if(op) {
		opc = opc.s(d, -fdir);
		if(opc == null)
		    op = false;
		else
		    if(!iter.go(opc, -fdir * i))
			op = false;
	    }
	}
    }

    /** A cell enumeration, with index.
     */
    public interface NEnum {
	/** Get the next cell.
	 */
	ZZCell nextCell();
	/** Get the index of the last returned cell from nextCell.
	 */
	int nth();
	/** Whether there are more cells.
	 */
	boolean more();
	/** Stop advancing in the current direction.
	 */
	void stop();
    }

    /** Return an enumeration that alternates between the directions.
     * @param c The cell to start from.
     * @param included Whether the first cell is also included.
     * @param d The dimension to go along.
     * @param fdir The direction to take the first step in.
     */
    public static NEnum alternate(final ZZCell c, final boolean included, final String d, final int fdir) {
	return new NEnum() {
	    /** Next cell in p or n direction.
	     */
	    ZZCell nextn = c.s(d, -fdir), nextp = c.s(d, fdir);

	    int ind = 0;

	    boolean started;

	    public ZZCell nextCell() {
		if(nextn == null && nextp == null) return null;
		if(!started) {
		    started = true;
		    if(included) return c;
		}
		// Trick: always change ind, only after see if we have something
		// to return. If not, recurse and get the next one from the other side.
		if(ind <= 0) {
		    ind = -ind;
		    ind ++;
		    if(nextp == null)
			return nextCell();
		    ZZCell ret = nextp;
		    nextp = nextp.s(d, fdir);
		    return ret;
		}
		if(ind > 0) {
		    ind = -ind;
		    if(nextn == null)
			return nextCell();
		    ZZCell ret = nextn;
		    nextn = nextn.s(d, -fdir);
		    return ret;
		}
		return null;
	    }
	    public int nth() {
		return fdir * ind;
	    }
	    public void stop() {
		if(ind >= 0) nextp = null;
		else nextn = null;
	    }
	    public boolean more() {
		return nextn != null || nextp != null;
	    }
	};
    }
}




````



### Attachment: ZZKeyBindings.java _(1.2 KB)_
````
/*   
ZZKeyBindings.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.awt.event.*;
import java.awt.*;

/** A generic keybindings driver interface.
 * The point of this interface is to allow experimentation 
 * with different ways of specifying keybindings in the ZigZag structure.
 */

public interface ZZKeyBindings {
String rcsid = "$Id: ZZKeyBindings.java,v 1.13 2000/09/19 10:31:58 ajk Exp $";
	/** Perform a particular key or mouse
	 * event associated with a particular view.
	 */
	void perform(InputEvent k, ZZView v, ZZView ctrlv, ZZScene xi);
}


````



### Attachment: ZZKeyBindings0.java _(1.4 KB)_
````
/*   
ZZKeyBindings0.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.awt.event.*;

/** A very simple keybindings class which is hardcoded for the cursor keys.
 * Does nothing else. OBSOLETE.
 */
 /*
public class ZZKeyBindings0 implements ZZKeyBindings {
public static final String rcsid = "$Id: ZZKeyBindings0.java,v 1.7 2000/09/19 10:31:58 ajk Exp $";
	ZZCell current;
	public void perform(KeyEvent k, ZZView v) {
	// XXX Hardcoded - should update automatically from the structure..
		switch(k.getKeyCode()) {
			case k.VK_UP: v.move(0,-1); break;
			case k.VK_DOWN: v.move(0,1); break;
			case k.VK_LEFT: v.move(-1,0); break;
			case k.VK_RIGHT: v.move(1,0); break;
		}
	}
}

*/
class LIJFSELFJLISEFJLSEFSF { }

````



### Attachment: ZZKeyBindings1.java _(10.1 KB)_
````
/*   
ZZKeyBindings1.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.awt.*;
import java.awt.event.*;

/** The first meaningful keybindings class.
 * A stateless class which looks along d.2 for a string matching 
 * the result of the getKeyText method of the java.awt.event.KeyEvent class.
 */

public class ZZKeyBindings1 implements ZZKeyBindings {
public static final String rcsid = "$Id: ZZKeyBindings1.java,v 1.61.2.2 2001/08/16 14:51:24 bfallenstein Exp $";
    public static boolean dbg = false;
    static final void p(String s) { if(dbg) ZZLogger.log(s); }
    static final void pa(String s) { ZZLogger.log(s); }

    /** Create ZZKeyBindings1.
        @deprecated Use the noarg constructor instead. */
    ZZKeyBindings1(ZZExec x) { this(); }
    ZZKeyBindings1() {}
   
    Point origpt;
    boolean dragging = false;

    public void perform(InputEvent ie, ZZView v, ZZView ctrlv, ZZScene xi) {
	ZZCell vcell = v.getViewcell();

	String t = null;
	p(" "+ie);
	if(ie instanceof KeyEvent) {
	    /*
	     * This is quite complicated - more complicated than it
	     * should be but Java seems to screw up key events quite
	     * nicely for us...
	     * We want to have Shift-Alt-X, for example, which on some
	     * Javas needs quite a bit of attention.
	     */
	    KeyEvent k = (KeyEvent) ie;
	    char c= k.getKeyChar();
	    int kc = k.getKeyCode();
	    String kt = KeyEvent.getKeyText(kc);
	    String kbychar = new String(new char[] {c});
	    p("Have: "+c+" "+kc+" '"+kt+"' '"+kbychar+"'");
	    if((c == k.CHAR_UNDEFINED  
		// k.CHAR_UNDEFINED changed between JDK1.1 and 1.2
		|| c == 0x0 || c == 0xFFFF // needed for cross-compiling
                || kc == k.VK_DELETE 
		|| kc == k.VK_BACK_SPACE)
		&& kc != 0)
		    t = kt;
	    else
		    t = kbychar;
	    p("Chose: "+t);
	    if(t.equals("\n")) t = "Enter";
	    if(t.equals("\t")) t = "Tab";
	    if(t.equals("\033")) t = "Esc";
	    if(t.equals("") ||
		Character.isISOControl(t.charAt(0)) ||
		k.isAltDown() || k.isControlDown() ||
		kt.equals("Left") || // These need shift.
		kt.equals("Right") ||
		kt.equals("Up") ||
		kt.equals("Down")
		) {
		    p("Maybe rechoosing");
		    if(kc != 0)
			t = kt;
		    if(k.isShiftDown()) t = "Shift-"+t;
	    }
	    if(k.isAltDown()) t = "Alt-"+t;
	    if(k.isControlDown()) t = "Ctrl-"+t;

	    p("KEYTEXT: '" + t + "', was by kt: '"+kt+"' and by char: '"
		    +kbychar+"'");
	    if(t==null) return;
	    perf(t, null, v, ctrlv, t, null, xi);
	} else if(ie instanceof MouseEvent) {
	    MouseEvent m = (MouseEvent)ie;
	    String modstr = "";

	    if(m.isAltDown()) modstr = "Alt-"+modstr;
	    if(m.isControlDown()) modstr = "Ctrl-"+modstr;
	    if(m.isShiftDown()) modstr = "Shift-"+modstr;

	    Point pt = new Point(m.getX(), m.getY());
	    String mec = null;
	    ZZCell targ = null;
	    if(m.getID() == m.MOUSE_CLICKED) {
		mec = "Clicked";
		dragging = false;
		// If it was a cell, give it as the target.
		// XXX Need we really do this here?
		Object ob = xi.getObjectAt(m.getX(), m.getY());
		if(ob instanceof ZZCell) targ = (ZZCell) ob;
		
		// Call applitude manager, to change app if necessary
		// (Actually, just realized: because we do this here, before
		//  we call perf(), the applitude bindings of the new
		//  applitude are used, which is exactly what we want!)
		ApplitudeMgr.clicked(vcell, xi, pt);
	    } else if(m.getID() == m.MOUSE_PRESSED) {
		mec = "Pressed";
		origpt = pt;
		dragging = false;
	    } else if(m.getID() == m.MOUSE_DRAGGED) {
		mec = "Dragged";
		if(!dragging) {
		    perf(modstr+"MouseStartDrag", null, v, ctrlv, null, origpt, xi);
		    dragging = true;
		}
	    } else if(m.getID() == m.MOUSE_RELEASED) {
		mec = "Released";
		dragging = false;
		// XXX EndDrag?
	    } else
		return;
	    int but = 0;
	    int mod = m.getModifiers();
	    if((mod & m.BUTTON1_MASK) != 0) but = 1;
	    else if((mod & m.BUTTON2_MASK) != 0) but = 2;
	    else if((mod & m.BUTTON3_MASK) != 0) but = 3;

	    t = modstr+"Mouse"+mec+but;

	    p("MOUSE: '"+t+"': event was "+m);

	    perf(t, targ, v, ctrlv, null, pt, xi);

	}
    }

    /** Get the key bindings mode cursor associated with this window.
     *  Does currently <em>not</em> create a new one if there is none.
     *  Instead, returns null.
     */
    public static ZZCell getModeCursor(ZZCell window) {
	return window.h("d.bind", 1, true);
    }

    /** Get the key bindings mode cell associated with this window.
     *  Set to default mode if no mode is there.
     */
    public static ZZCell getMode(ZZCell window) {
	ZZCell c0 = getModeCursor(window);
	if(c0 == null) {
	    p("NO BIND YET: SET CURS");
	    c0 = window.N("d.bind", 1);
	    ZZCell cur0 = ZZDefaultSpace.findOnSystemlist(
		    window.getSpace(), "Bindings", false).s("d.1", 1);
	    ZZCursorReal.set(c0, cur0);
	    ZZCursorReal.setColor(c0, new Color(0xaf5a00));
	}
	return ZZCursorReal.get(c0); 
    }

    void perf(String id, ZZCell target,
		ZZView v, ZZView ctrl, String key, Point pt, ZZScene xi) {
	p("PERF: '"+id+"'");
	ZZCell vcell = v.getViewcell();
	ZZCell accursed = ZZCursorReal.get(vcell);
	ZZCell cvcell = ctrl.getViewcell();
	ZZCell cur = getMode(vcell);
	p("BIND CURS: "+cur+" "+(cur!=null?cur.getID():null));
	
	/** Use applitude bindings?
	 * As not all views show applitude data, views which do have to
	 * have an "appbindings" structparam to declare the bindings of the
	 * applitude currently prefered by this window shall be used.
	 */
	boolean useAppBinds = false;
	
	/** Is the binding found an applitude binding?
	 * This affects how the bindings mode is changed.
	 */
	boolean isAppBind = false;
	
	ZZCell raster = 
	    ZZDefaultSpace.findInheritableParam(vcell, "View");
	if(raster != null) raster = ZZCursorReal.get(raster);
	if(raster != null) raster = raster.h("d.clone", -1);
	if(raster != null) raster = raster.s("d.1", 2);
	if(ZZDefaultSpace.findInheritableParam(raster, "appbindings") != null)
	    useAppBinds = true;
	if(raster != null) raster = 
	    ZZDefaultSpace.findInheritableParam(raster, "databindings");
	if(raster != null) raster = raster.intersect("d.1",1,cur,"d.clone",1);

	ZZCell craster = 
	    ZZDefaultSpace.findInheritableParam(cvcell, "View");
	if(craster != null) craster = ZZCursorReal.get(craster);
	if(craster != null) craster = craster.h("d.clone", -1);
	if(craster != null) craster = craster.s("d.1", 2);
	if(craster != null) craster = 
	    ZZDefaultSpace.findInheritableParam(craster, "ctrlbindings");
	if(craster != null) craster = craster.intersect(
	    "d.1", 1, cur, "d.clone", 1);

	ZZCell binding = null;
	if(raster != null) {
	    binding = ZZDefaultSpace.findInheritableParam(raster, id);
	    p("Tried by view");
	}
	if(binding == null && useAppBinds) {
	    ZZCell app = ApplitudeMgr.getAppBindsForWin(vcell);
	    binding = ZZDefaultSpace.findInheritableParam(app, id);
	    p("Tried by applitude");
	    if(binding == null && key != null && key.length() > 0) {
		binding = ZZDefaultSpace.findInheritableParam(app, "INSERT");
		p("Tried by applitude INSERT");
	    }
	    if(binding == null) {
		binding = ZZDefaultSpace.findInheritableParam(app, "DEFAULT");
		p("Tried by applitude DEFAULT");
	    }
	    if(binding != null)
		isAppBind = true;
	}
	if(binding == null && craster != null) {
	    binding = ZZDefaultSpace.findInheritableParam(craster, id);
	    p("Tried by ctrl view");
	}
	if(binding == null) {
	    binding = ZZDefaultSpace.findInheritableParam(cur, id);
	    p("Tried by cur");
	}
	if(binding == null && key != null && key.length() == 1) {
	    binding = ZZDefaultSpace.findInheritableParam(cur, "INSERT");
	}
	if(binding == null) {
	    binding = ZZDefaultSpace.findInheritableParam(cur, "DEFAULT");
	    p("Tried by DEFAULT");
	}
	if(binding == null && 
	   ZZDefaultSpace.findInheritableParam(cur, "EDITBINDS") != null) {
	    ZZCell cellview = accursed.h("d.cellview", true), ecur = null;
	    p("cellview: "+cellview);
	    if(cellview != null)
		cellview = cellview.s("d.1", 2);
	    if(cellview != null)
		cellview = ZZDefaultSpace.findInheritableParam(cellview, "EditBindings");
	    if(cellview != null)
		ecur = cellview.s("d.1", 1); 
	    p("editbinds cur: "+ecur);
	    if(ecur == null)
		ecur = ZZDefaultSpace.findOnSystemlist(vcell.getSpace(), 
		    "EditBindings", true).getOrNewCell("d.1", 1);
	    if(ecur != null) {
		binding = ZZDefaultSpace.findInheritableParam(ecur, id);
		p("Tried by editbinds");
		if(binding == null && key != null && key.length() == 1) {
		    binding = ZZDefaultSpace.findInheritableParam(ecur, "INSERT");
		    p("Tried by editbinds INSERT");
		}
		if(binding == null) {
		    binding = ZZDefaultSpace.findInheritableParam(ecur, "DEFAULT");
		    p("Tried by editbinds DEFAULT");
		}
	    }
	}

	p("BINDING: "+binding);
	if(binding != null) {
	    ZZCell bc = binding.s("d.1", 1);
	    p("Bind command cell: "+bc);
	    if(bc == null) {
		    System.out.println("AUGH! NO BINDING");
		    return;
	    }
	    ZZCell nextstate = bc.h("d.3", -1, true);
	    if(nextstate != null) {
		if(!isAppBind)
		    ZZCursorReal.set(getModeCursor(vcell), nextstate);
		else
		    ApplitudeMgr.setAppBindsForWin(vcell, nextstate);
	    }
	    ZZCommand comm = null;
	    if(bc.getRootclone().s("d.xeq") == null)
		comm = ZZCommand.getCommand(bc);
	    if(comm != null)
		comm.execCallback(
			target,
			v, ctrl,
			key, pt, xi
			);
	    else
	        new ZZPrimitiveActions().execCallback(
			bc, 
			target,
			v, ctrl,
			key, pt, xi
			);
	    return;
	} else if (key != null && key.equals("Esc")) {
            v.getViewcell().getSpace().undo();
        }
    }
}


````



### Attachment: ZZKeyHacks.java _(3.5 KB)_
````
/*   
ZZKeyHacks.java
 *    
 *    Copyright (c) 1999, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Benja Fallenstein
 */
package org.gzigzag;
import java.awt.*;
import java.awt.event.*;

/** Hacks to work around Java's inconsistent, ideosyncratic key events.
 *  Everything in this class is static, but there are (static) variables
 *  for the "detected state of the system": e.g., how this Java VM handles
 *  umlauts.
 *  <p>
 *  Currently, detects whether we get umlauts through KEY_PRESSED; if not,
 *  invokes them at KEY_TYPED.
 */

public class ZZKeyHacks {
public static final String rcsid = "$Id: ZZKeyHacks.java,v 1.1.2.2 2001/04/08 15:17:51 bfallenstein Exp $";
    public static boolean dbg = false;
    static final void p(String s) { if(dbg) ZZLogger.log(s); }
    static final void pa(String s) { ZZLogger.log(s); }

	// Java is really screwy about what keyevents get
	// pressed and what are typed. We want to catch both.

	// It seems that at least on my platform and keybindings,
	// this is the totally unreasonable but working way to get
	// them. 

	// Ouch.

        // FIXME: This is a REALLY REALLY BAD QUICK HACK to make the
        // Finnish special letters work.  The problem?  We don't get a
        // KEY_PRESSED for them.  Damn Java!

    /** Whether we ever got an umlaut from a KEY_PRESSED event.
     *  If this is set to true, we ignore KEY_TYPED events. If it is set to
     *  false, KEY_TYPED events with umlauts in them get processed like
     *  KEY_PRESSED events. As KEY_PRESSED events occur before KEY_TYPED 
     *  events, this is a gain.
     */
    static boolean gotPressedUmlaut;

    /** The start of the Unicode character range we treat as umlauts. */
    static final int firstumlaut = 0x00C0;

    /** The end of the Unicode character range we treat as umlauts. */
    static final int lastumlaut = 0x00FD;

    /** Do the hacks on this key event.
     *  Currently, does the umlaut trick, as well as the testing whether we
     *  need it.
     */
    static public KeyEvent keyEventHack(KeyEvent e) {
	if(gotPressedUmlaut) return e;
		
        int id = e.getID(), c = e.getKeyChar();
	boolean umlaut = (c >= firstumlaut) && (c <= lastumlaut);
	
	if(!umlaut) return e;

	if(id == e.KEY_PRESSED) {
	    gotPressedUmlaut = true;
        } else if(id == e.KEY_TYPED) {
	    return new KeyEvent(e.getComponent(), e.KEY_PRESSED, e.getWhen(), 
				e.getModifiers(), e.getKeyCode(),
				e.getKeyChar());
        }

	return e;
    }

    /** Reset the state, so as if the program was fired up anew.
     *  This sets back all information gathered about the Java VM so far
     *  and re-initializes the class. Currently this is used for testing
     *  purposes only: the TestUmlauts JUnit test suite needs to be able to
     *  run different tests emulating different kinds of VMs.
     */
    static public void reset() {
	gotPressedUmlaut = false;
    }

    // Initialize the class by calling reset() a first time.
    { reset(); }
}


````



### Attachment: ZZLocalDimension.java _(2.4 KB)_
````
/*   
ZZLocalDimension.java
 *    
 *    Copyright (c) 2000, Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Tuomas Lukka
 */
package org.gzigzag;
import java.util.*;

/** Dimension-centric implementation of a locally 
 * stored dimension. 
 */
public class ZZLocalDimension extends ZZDimension {
public static final String rcsid = "$Id: ZZLocalDimension.java,v 1.14 2000/11/30 08:44:32 ajk Exp $";
	public static final boolean dbg = true;
        final static void p(String s) { if(dbg) ZZLogger.log(s); }
        final static void pa(String s) { ZZLogger.log(s); }

	/** Connections to the positive direction. */
	Hashtable cp = new Hashtable();
	/** Connections to the negative direction. */
	Hashtable cm = new Hashtable();

	public ZZCellHandle s(ZZCellHandle c, int steps, ZZObs o) {
		String s = c.id;
		if(o != null) triggers.addObs(s, o);
		if(steps>0)
			while(steps-- > 0 && s != null) {
			    s = (String)cp.get(s);
			    if(o != null) triggers.addObs(s, o);
			}
		else
			while(steps++ < 0 && s != null) {
			    s = (String)cm.get(s);
			    if(o != null) triggers.addObs(s, o);
			}

		if(s==null) return null;
		return (ZZCellHandle)space.getCellByID(s);
	}
	public void connect(ZZCellHandle c, ZZCellHandle d) {
		disconnect(c, 1);
		disconnect(d, -1);
		/* XXX: This is from 0.3 branch, don't know if this
		  should be chosen instead of the above 
	    if(cp.get(c.id) != null ||
	       cm.get(d.id) != null)
		    throw new ZZConnectWouldBreakError("localdim");
		*/
		cp.put(c.id, d.id);
		cm.put(d.id, c.id);
		triggers.chg(c.id);
		triggers.chg(d.id);
	}
	public void disconnect(ZZCellHandle c, int dir) {
		String o;
		if(dir>0) {
			o = (String)cp.get(c.id);
			if(o!=null) {
				cp.remove(c.id);
				cm.remove(o);
			}
		} else {
			o = (String)cm.get(c.id);
			if(o!=null) {
				cm.remove(c.id);
				cp.remove(o);
			}
		}
		triggers.chg(c.id);
	}

}

````



### Attachment: ZZLogger.java _(2.1 KB)_
````
/*   
Main.java
 *    
 *    Copyright (c) 1999, 2000 Ted Nelson and Tuomas Lukka
 *
 *    You may use and distribute under the terms of either the GNU Lesser
 *    General Public License, either version 2 of the license or,
 *    at your choice, any later version. Alternatively, you may use and
 *    distribute under the terms of the XPL.
 *
 *    See the LICENSE.lgpl and LICENSE.xpl files for the specific terms of 
 *    the licenses.
 *
 *    This software is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the README
 *    file for more details.
 *
 */
/*
 * Written by Antti-Juhani Kaijanaho and Tuomas Lukka.
 */

package org.gzigzag;
import java.lang.reflect.*;
import java.io.*;

/** A static package for logging things into a file.
 * Used for providing ZZ developers with debug output to help them
 * solve crashes.
 */

public class ZZLogger {
    public static PrintWriter logfile = null;

    private static boolean syslog = false;

    public static void tryInitSyslog() {
        try {
            SysLogger.init();
        } catch (UnsatisfiedLinkError e) {
            exc(e);
            return;
        }
        syslog = true;
    }

    public static void exc(Throwable t, String s) {
	log(""+s);
	exc(t);
    }

    public static void exc(Throwable t) {
	if(t instanceof InvocationTargetException) {
	    Throwable t1 = ((InvocationTargetException)t).getTargetException();
	    verblog("InvokeException content: ");
	    exc(t1);
	}
        log(""+t);
	t.printStackTrace();
	if(logfile != null) {
	    t.printStackTrace(logfile);
	    logfile.flush();
	}
    }

    public static void log(String s) {
        System.err.println(s);
        if (syslog) SysLogger.log(s);
        filelog(s);
    }

    private static void filelog(String s) {
        if (logfile != null) {
            logfile.println(s);
            logfile.flush();
        }
    }

    public static void verblog(String s) {
        if (syslog) SysLogger.verblog(s);
    }
}

````

## Response:
Two of the uploads, `ZZCell.java` and `ZZDefaultSpace.java`, didn't come through in the pasted documents, and they matter most for this question. I'll read them from disk first.

Reading these files changes the answer in several ways. Two of the uploads, `ZZCell.java` and `ZZDefaultSpace.java`, weren't in the pasted context, so I read them from disk. I only skimmed them (API surface and dependency grep), as I did with `ZZUtil.java` and `ZZPrimitiveActions.java`. I haven't compiled anything.

## What changes

1. **The structure core is AWT-free.** `ZZCell`, `ZZSpace`, `ZZDimSpace`, `ZZDimension` and `ZZLocalDimension` import only `java.util`. `ZZCursorReal` touches AWT in just four color methods. Last time I rated the coupling "moderate", and it's lower than that.
2. **The dependency closure is now measurable.** Besides the uploaded files, the core needs these small-looking classes that I haven't seen: `ZZError`, `Span`, `SpanSet`, `StringScroll`, `LoopDetector`, `ZZInfiniteLoop`, `ZZConnectWouldBreakError`, `SyntaxError` and `SysLogger`.
3. **There are only three cut points.**
   - `ZZObsTrigger` calls `ZZUpdateManager.chg()`. Replace it with a listener hook.
   - `ZZPath` needs `ZZDefaultSpace.getPossDerefCell`. Move that helper.
   - `ZZCursorReal` fires trigger commands through `ZZCommand`, which drags in `ZZView`, `ZZScene` and `ZOb`. Put an interface in between.
4. **`ZZDefaultSpace` isn't a space.** It's a 1,087-line static grab-bag, and I'd split it. The structure conventions (`findInheritableParam`, `findOnSystemlist`, `getPossDerefCell`, `readZOb`, mark and inbuf helpers) belong in the core. The bootstrap seeding (`create()`, `newViewPair`, `newToplevelView`, `getScene`) pulls in `ApplitudeMgr` and the view stack and stays with the UI.
5. **There's a layer I missed: cursors live in the structure.** They're stored as cells on `d.cursor`, `d.cursor-list` and `d.cursor-cargo`, so `ZZCursor`, `ZZCursorReal` and `ZZCursorVirtual` belong in the core. `ZZPrimitiveActions` is the command vocabulary on top. It has roughly 120 action IDs (CNCT, DISC, CLONE, EXCISE, HOP, NEW, GOTO, UNDO and so on), and my grep found only a handful of lines touching views or AWT types.
6. **Some files can simply be deleted:**
   - `ZZEvObs` is identical to `ZZObs`.
   - `ZZExec` is superseded by `ZZCommand`, per its own comment.
   - `ZZKeyBindings0` and `ZZSlicedDimSpace` are commented-out bodies with junk placeholder classes.
   - `ZZKeyHacks` is an umlaut workaround for 2001-era JVMs.
   - `ZZDrawing` reflects around Java2D, which you can now use directly.

## Revised project order

1. **Observer cut.** This is the same as before and takes a few hours. But `ZZDimension` and `ZZDimSpace` each allocate their own `ZZObsTrigger`, so it's the foundation for step 2, not a standalone deliverable.
2. **Headless core.** This is the main project now.
   - Take `ZZCell`, `ZZCellHandle`, `ZZSpace`, `ZZDimSpace`, `ZZDimension`, `ZZLocalDimension`, `ZZRODimension`, `ZZSpacePart`, `ZZConnection`, `ZZPath`, `ZZIter`, `ZZTraverseCB`, `ZZLogger` and the observer pair.
   - Add the cursor classes with `ZZCommand` abstracted away.
   - You'd then have a working in-memory ZigZag space, since `ZZDimSpace` is concrete and `ZZLocalDimension` is two hashtables.
   - Stub the missing classes and drop `SysLogger` from `ZZLogger`.
3. **Headless command layer.** Extract the structural subset of `ZZPrimitiveActions`, such as connect, disconnect, clone, excise, hop and new. Leave the view- and window-driven actions behind.
4. **View layer.** This is still a rewrite, as I said before, with two refinements.
   - The real coupling point is `ZZKeyBindings1.perform`, which uses `ApplitudeMgr` and the view cells.
   - The key-chord naming (`Ctrl-Alt-X`, `Shift-Left`) and the layered binding lookup (view, applitude, control view, mode cursor, `INSERT`, `DEFAULT`) are worth preserving as an AWT-free resolver.
5. **Persistence.** Nothing in these files persists. `ZZDimSpace` is hashtables only, and the Makefile references a `storage/` package I haven't seen. `ZZTraverseCB` is the natural seam for import and export.

## Problems I noticed (verify before relying on them)

- **`ZZLocalDimension.s()`** calls `triggers.addObs(s, o)` after `s` may have become null at a rank end. `addObs` does `Hashtable.get(null)`, which throws `NullPointerException`. As written, any observed step off the end of a rank should crash, so make that your first unit test.
- **`ZZDimension.findText`** ignores its `dir` parameter and always searches forward, so `ZZPath`'s `FIND dim -1 str` would misbehave.
- **`ZZIter.alternate(...)`**, the enumeration version, returns null for an isolated cell even with `included=true`. The callback version includes it.
- **`ZZDimSpace.getCellByID(part, s, o)`** dereferences `p.id` before its null check.
- **Observer leak and locking:**
  - Every dimension and space allocates a `ZZObsTrigger` that stays in a static list forever, and every `chg(ZZObs)` walks that whole list.
  - That also makes the lock-ordering risk I flagged earlier more concrete: an instance lock, then `obsQueue`, then other instances' locks.
  - The code mostly runs on one thread, which limits the practical risk.

If you upload the missing small classes (`Span`, `ZZError`, `LoopDetector` and the others), I can check whether the core compiles standalone and list exactly what to stub.

## Prompt:
Please explain the concept of a Dimension Space  or zzDimSpace as inferred from the available source code

## Response:
A ZZDimSpace is a ZigZag space in which each dimension is an object that owns the connections for that dimension. A cell is only an ID. Everything below is inferred from the source, and where I'm guessing I say so.

## The model underneath

ZigZag, as these files implement it, has three ideas:

- **Cells** hold content, either text or a `Span` (a reference into a scroll).
- **Dimensions** are named, like `d.1` or `d.cursor`.
- **Connections** link two cells along one dimension. Each cell has at most one neighbor in the positive direction and one in the negative direction on any dimension.

That last rule means each dimension partitions the cells into **ranks**, which are linear sequences (possibly circular). A cell can sit on a different rank in every dimension. This is why `s(dim, steps)` ("step") and `h(dim, dir)` ("headcell", the end of the rank) are the basic navigation operations.

`ZZSpace` is the abstract contract: a home cell, lookup by ID, a list of dimensions, and stubs for undo, commit, freeze and thaw. `ZZDimSpace` is the concrete implementation, and its class comment calls it "dimension-centric".

## Dimension-centric: where the links live

An alternative design would store links inside each cell, such as a record with a `+next` and `-next` per dimension. This design inverts that. A `ZZDimension` is "called with the cell objects" and answers questions about its own dimension. Only three operations are abstract:

- `s(cell, steps, obs)`
- `connect(c, d)`
- `disconnect(c, dir)`

Everything else is built on top of those in the base class:

- `h` (headcell) walks the rank.
- `insert` is a sequence of disconnects and connects.
- `excise` removes a cell and bridges the gap.
- `hop` moves a cell along its rank.
- `findText` searches the rank.

Subclasses may override these for speed, but they don't have to. The default dimension, `ZZLocalDimension`, is just two hashtables of IDs, a forward map and a backward map:

```
connect(A,B); connect(B,C)   on d.x

cp (forward):  A→B  B→C
cm (backward): B→A  C→B

s(A, 2) = C     s(C, -1) = B     h(A, -1) = A
```

`connect` first disconnects `c`'s forward link and `d`'s backward link. That is what enforces the one-neighbor rule. For circular ranks, `h()` has a tie-break: it returns the cell with the lexically largest ID, so a loop still gets a deterministic "head".

## What the space itself holds

`ZZDimSpace` is mostly a registry:

| Field | Maps | Purpose |
|---|---|---|
| `dims` | name → `ZZDimension` | Dimensions, created lazily |
| `cells` | id → `DimCell` | Cached cell handles |
| `contents` | id → String or Span | Cell content |
| `spaceParts` | name → `ZZSpacePart` | Virtual regions |
| `spanset` | spans → ids | Optional overlap search |
| `nextID` | counter | ID allocation |

Several things follow from this layout:

- **A cell is an ID plus a pointer to its space.** `DimCell` extends `ZZCellHandle`, and its comment says two cell objects with the same ID may exist because "we're aiming for Java 1.1 which does not have weak references". Equality is by ID. Content and links are stored in the space and dimensions, not in the cell object.
- **Cell operations just delegate.** `cell.s(dim, n)` calls `d(dim).s(this, n)`, and `cell.connect(dim, to)` calls `d(dim).connect(...)`.
- **Dimensions are created on first use.** `d(name)` calls the overridable `createDimension`. The default makes a `ZZLocalDimension`, except for `d.cellcreation`, which is a read-only `IDDimension`. It computes "the next cell by creation order" arithmetically from numeric IDs, with no storage at all. Names containing `:` are handed to a space part.
- **The space describes itself in its own structure.** When a dimension is first created, `updateMasterDimList` appends its name as a cell on the home cell's `d.masterdim` rank, so `dims()` reads the dimension list out of the structure.
- **Deleting a cell** means excising it from every dimension.

## IDs

- The home cell is `"1"`, and new cells take IDs from the `nextID` counter.
- `getCellByID` bumps the counter whenever it sees an ID at or past it. I'd guess this is so a space loaded from storage doesn't reissue IDs.
- `"part:xyz"` addresses a cell in a space part.
- `"id@spaceid"` seems intended for cross-space references. The code strips the suffix if it names this space.

## Space parts: virtual regions

`ZZSpacePart` is marked experimental. A part owns the cells whose IDs start with its name, plus dimensions named `part:something`, and it computes text and connections algorithmically. The class comment gives the example of a calendar with thousands of years at nanosecond precision, where a cell's ID encodes the moment and the dimensions compute neighbors. `ZZCellHandle.parsedID` exists so the part can keep a decoded form of the ID, such as coordinates, on the handle.

## Observation

Reading with a `ZZObs` registers a dependency. `s(..., obs)` registers the observer against the cells it passes over, and `getText(obs)` registers it against the cell's text. Each dimension has its own `ZZObsTrigger` and the space has `textTrig` for content. Changes call `trigger.chg(id)`, which queues the dependent observers. It works like a reactive "recompute when what you read changes" system. The windows layer uses it to rebuild itself when the structure under it changes.

## Conventions on top

The space itself doesn't give dimensions any meaning. Meaning comes from naming conventions, which the other classes rely on:

- `d.clone`: clones share content, because text reads and writes go to the root clone.
- `d.cursor`, `d.cursor-list` and `d.cursor-cargo`: cursors are stored as cells in the structure.
- `d.1`, `d.2` and `d.3`: generic dimensions used for parameter lists, such as `ZZPath`'s `STEP dim n`.
- `d.slices`: sliced spaces. The commented-out `ZZSlicedDimSpace` composed several spaces using IDs of the form `slice-origid`.

## What's not here

`ZZDimSpace` as shown is purely an in-memory base class. These all look like extension points for subclasses I haven't seen, but that is an inference:

- Undo, redo and commit are inherited no-ops.
- `freeze` and `thaw` do nothing.
- `rmAllObs` does nothing, and `findLongRankHeads` returns null.
- `getRankNames` throws.
- There is no persistence.

## Prompt:
Do you see any code for persistence of zzStructures to text files?

## Response:
Let me search the uploads rather than answer from memory.

No. There is no code in these files that writes a ZZ structure to a text file or reads one back. What exists is a debug dump, an interface with no implementation, and references to a module that isn't included.

**What's there**

- **`ZZUtil.dumpSubSpace(cell, dims[])`** is the closest thing. It walks the cells reachable along the given dimensions and prints each cell and its ±1 neighbors to `System.out`. Its own comment calls it "VERY naive". It has no inverse and no file output, and it prints `ZZCell.toString()`, which isn't a stable serialization. The call in `ZZDefaultSpace` (line 529) is commented out.
- **`ZZTraverseCB`** is the persistence-shaped interface. It has `start(home)`, `cell(cur, dim, dir, which, content)`, `connect(c1, dim, dir, c2)` and `finish()`. Its comment says "An interface for creating a ZZ space through traversal", which makes it a loader-side visitor. Nothing in the uploaded files implements or calls it, so the code that would walk a file and drive it, and the code that would walk a space and emit these events, are both elsewhere.
- **`Dumper.Create`, `Dumper.Read`, `Dumper.Write`, `Dumper.Dump`, `Dumper.Enter` and `Dumper.ChangeID`** are menu entries that `ZZPrimitiveActions` seeds into the default structure. They are strings that dispatch to a `Dumper` module through `ZZModule.getModule("Dumper")`, which loads `org.gzigzag.module.Dumper`. That class isn't uploaded. Going by the names, it very likely handles reading and writing spaces, but I can't see what format it uses.

**Other I/O that isn't persistence**

- `ZZLogger` writes log lines.
- `ZZPrimitiveActions.textlog` is a `PrintWriter` that records typed input.

**Where else it could be**

- The Makefile mentioned a `storage/` package (with `Recs.java`), which I haven't seen. `ZZDimSpace` here is in-memory only, with `contents`, `cells` and the dimensions all in hashtables. A subclass in `storage/` is the natural place for undo, commit and on-disk state, since `ZZSpace` defines `stamp`, `undo`, `redo` and `commit` as no-op hooks.
- The `Modules/` directory may hold the `Dumper`.
- Any `ZZTraverseCB` implementation could live in either.

If you upload `Dumper.java` and whatever is in `storage/`, I can describe the file format. The Makefile's module list and a recursive `grep -rl "ZZTraverseCB"` over the full tree would tell you quickly which files to look at.

## Prompt:
How would you define cargo based on the source code?

## Response:
From the source, cargo is a cell that rides on a cursor. It sits on the `d.cursor-cargo` rank, behind the cursor cell, and it resolves to whatever that cursor points at. No file defines the term, so this is inferred from `ZZCursorReal` and its callers.

## The structure

Cursors are stored in the ZZ structure as cells on three dimensions:

```
        d.cursor (+)                d.cursor-cargo (+)
 [A] ─────────────────▶ [K1] ─────────────────────▶ [view 1] ──▶ [view 2]
 accursed cell          cursor cell (head)              cargo
                         │ d.cursor-list (+)
                         ▼
                        [K2] ──▶ [other cargo...]      (second cursor, also on A)
```

- **Accursed cell:** the cell being pointed at. The word appears in `ZZTextView` and `ZZCursorReal`.
- **Cursor cell:** the real cursor, connected negwards to the accursed cell on `d.cursor`. Extra cursors on the same cell chain along `d.cursor-list`.
- **Cargo:** any cell posward of the cursor cell on `d.cursor-cargo`.

Resolving a cargo cell works like this, from `ZZCursorReal.get(x)`:

```
x.h("d.cursor-cargo", -1)   // go to the cursor cell at the head of the cargo rank
 .h("d.cursor-list", -1)    // go to the head of the cursor list
 .s("d.cursor", -1)         // step back to the accursed cell
```

So the cargo cell doesn't point anywhere itself. It inherits the target of the cursor it's attached to. Move the cursor with `setcursor`, and every cargo cell on that rank now resolves to the new cell.

## What lives on the cursor cell

The cursor cell at the head of the rank also holds the cursor's state:

- **Offset:** its text is the text offset, with `NO_OFFSET` stored as an empty string.
- **Color:** the text of its `d.1` neighbor is the cursor's RGB value.

Cargo cells therefore share one offset and one color, because those live on the head.

## What cargo is used for

1. **Views.** A view cell is cargo. `newToplevelView` either inserts the new view cell into an existing cursor's cargo rank (`cursorCargo.insert("d.cursor-cargo", 1, vc)`) or gives it a private cursor with `vc.N("d.cursor-cargo", -1)` and `ZZCursorReal.set(...)`. `ZZPhotoView` and `ZZTextView` then call `ZZCursorReal.get(viewCell)` to find what they should show. Two views on one cargo rank follow the same cursor.
2. **Pointer indirection.** Any cell can become a pointer. `setcargo(cargo, c)` creates a cursor cell behind it if none exists, then points that cursor at `c`. `setDimFromCell` uses this for dimension lists, and the comment on `getPossDerefCell` describes "a pointer (via d.cursor-cargo and d.cursor)". Helpers such as `ZZPath`'s `drdim` call that dereference, so a path step can name its dimension through a pointer cell.
3. **Triggers.** After a cursor change, `trigger()` walks the cargo rank from the head. Any cargo cell with a `d..cursor-trigger` connection runs the command at the head of that rank, with loop detection. So cargo can carry behavior that fires when the cursor moves.

Related operations:

- `attach(which, where)` hangs one cargo cell on another's rank so they share a cursor.
- `delete(c)` removes a cursor cell once its last cargo is gone.
- `set(start, c)` has a heuristic. If `start` isn't already a cursor or on a cursor list, it creates the cargo structure. Otherwise it just moves the cursor.

## What's inferred

- The code never explains why it's called "cargo". I'm reading it as "what the cursor carries".
- I haven't seen the `.zz` data that sets up the default structure. `ZZDefaultSpace.create` builds it, and I only skimmed that.
- `getPossDerefCell` looks like it can loop forever. It calls `ZZCursorReal.get(c)` on the original `c` each time, not on `cur`, so for a pointer cell it keeps getting the same non-null answer. The `XXX LoopDetector` comment suggests the author knew it was unfinished. It's worth a test.

## Prompt:
Which named system level dimensions (ex: d.cellcreation) can you identify in the source, and what is the apparent function of each?

## Response:
I found about 30 distinct `d.*` names in the source. They fall into three groups: the ones the space implementation itself depends on, the ones the cursor system uses, and conventions the UI and command layers use. I'm treating the first two groups as system-level. Functions are inferred from usage, and nothing documents them directly.

## Space infrastructure

| Dimension | Apparent function |
|---|---|
| `d.cellcreation` | Lists cells in creation order. It's the read-only `IDDimension` in `ZZDimSpace`, computed from numeric IDs with no storage. `ZZSpace.cells()` uses it to enumerate every cell. |
| `d.masterdim` | The registry of all dimensions. Each name is a cell on a rank from the home cell, appended by `updateMasterDimList` when a dimension is first created. `ZZSpace.dims()` reads it. |
| `d.slices` | Chains the home cells of slices (sub-spaces). `ZZSpace.cells()` follows it after finishing one slice's creation rank. The commented-out `ZZSlicedDimSpace` creates it as a special `SlicedHomes` dimension. |
| `d.system` | A named-entry list hanging off the home cell. `findOnSystemlist(space, "Name", create)` searches it by text. It holds the space's bookkeeping cells, such as `Actions`, `DimLists`, `ClientCell`, `SysCursors`, `Windows`, `Bindings`, `EditBindings`, `Input` and `Views`. `findOnClientlist` is an alias for it. |
| `d.clone` | Clone chains. `getRootclone()` is `h("d.clone", -1)`, and `DimCell.getText` and `setText` delegate to the root clone, so clones share content. It's also used to select entries: `ZZCommand.getCommand` treats a cell with a clone or a `d.1` neighbor as a possible object definition, and `ZZKeyBindings1` intersects `d.1` with `d.clone` to find the bindings in the current mode. |
| `d.1`, `d.2`, `d.3` | Unreserved general-purpose dimensions. By convention `d.1` is the parameter or value rank, `d.2` is the next item or list, and `d.3` is a sub-structure to recurse into. `ZZPath` reads its operation arguments from `d.1` and the next operation from `d.2`. The generated `readParams` code in `ZZPrimitiveCommand` uses all three. |
| `d.xeq` | A flag dimension. If the root clone of a code cell has a `d.xeq` neighbor, execution goes to the Flowing Clang interpreter instead of the primitive-action dispatcher. |
| `version:list`, `version:home` | Not `d.*` names. They're prefixed dimensions on the master list, with `version` presumably a space part. |

The official list written by `ZZDefaultSpace.create()` contains only `d.1`, `d.2`, `d.3`, `d.xeq`, `d.clone`, `d.system`, `d.cellcreation`, `d.masterdim` and the two `version:` entries. A commented-out longer list adds most of the names below.

## Cursor system

| Dimension | Apparent function |
|---|---|
| `d.cursor` | Links an accursed cell to its first cursor cell. |
| `d.cursor-list` | Chains additional cursors that point at the same cell. |
| `d.cursor-cargo` | Attaches cargo cells behind a cursor. The head holds the offset, and its `d.1` neighbor holds the color. |
| `d..cursor-trigger` | Links a cargo cell to a command. The spelling with two dots is as it appears in the source. |

`ZZSpace`'s own comment says the system dimensions "not generally used by the user" include `d.cursor` and `d.cursor-cargo`.

## Conventions in the UI and command layers

| Dimension | Apparent function |
|---|---|
| `d.view` | Chains the view cells under `ClientCell`. |
| `d.ctrlview` | Pairs a control view with its data view, at most two cells. `ZZViewComponent.redoCtrls` enforces that. |
| `d.dims` | A view's list of displayed dimensions, whose entries are pointers (cargo). `getDimList` dereferences them. |
| `d.bind` | A window's key-bindings mode cursor. |
| `d.cellview` | Looks up a per-cell edit-bindings override in `ZZKeyBindings1`. |
| `d.mark`, `d.mark-set` | The marked-cell set for a view. `d.mark` chains relation cells, and each one points to the marked cell via `d.mark-set`. Toggling a mark deletes or adds a relation cell. |
| `d.color` | Background and foreground colors for windows, and a cursor-mode color. |
| `d.bounds` | Window position and size as four integer cells. |
| `d.photo` | The URL of the image `ZZPhotoView` displays, read with `h("d.photo", 1)`. |
| `d.help` | Help text attached to a view cursor. |

## Names that appear but I couldn't pin down

- **`d.handle`, `d.byfield`, `d.headers`:** these only appear in the commented-out dimension lists. Going by the names, they relate to cell handles, field-based indexing and rank headers, but I have no usage to confirm that.
- **`d.preflets`, `d.slicesame`:** these only appear in the dead `ZZSlicedDimSpace`.
- **`d.dim`:** this appears only in a commented-out line.

I only searched the uploaded files. The `Modules/`, `flowing/` and `clang/` directories likely define more dimension names.

## Prompt:
What functionality can you infer that might be implemented in the data for the system, as zzCells connected in specific dimensions?  For example, some code may look for property lists in the data cells.

## Response:
I've finished reading the bootstrap code in `ZZDefaultSpace` and `ZZPrimitiveActions`, and I'm now pulling it together. The main finding is that large parts of the application are data in the space, not code.

## 1. Property lists: a name on `d.2`, values on `d.1`, inheritance on `d.3`

`findInheritableParam(start, id)` scans the `d.2` rank for a cell whose text equals `id`. At each cell it also searches the head of that cell's `d.3` rank recursively, so `d.3` acts as an "inherit from" link. Values hang off the parameter cell along `d.1`. Typed readers sit on top:

- `paramIntA` and `paramFloatA` read the `d.1` rank as numbers.
- `findInheritableParamFont` reads a font name and then a size.
- Booleans are the text `"true"` or `"false"`.
- Colors are `0xffffff` strings or RGB integers.

Inheritance is built by linking cells. `ZP.inh(depth)` connects a shared "depth = 5" cell into the `d.3` rank of several views, so they all inherit it.

## 2. Objects instantiated from cells (ZObs)

`readZOb(cell)` goes to the root clone, takes the next `d.1` cell as a class name, and takes the cell after it as the head of a parameter list:

```
[Vanishing] ─d.1→ [VanishingView] ─d.1→ [ ] ─d.2→ [depth] ─d.1→ "5"
                                          │d.2
                                        [varsize] ─d.1→ "true"
```

A plain name loads `org.gzigzag.<Name>`. A dotted name like `Notemap.Star` or `Prez.R` loads the `Notemap` or `Prez` module and asks it for the `Star` or `R` object. The `.zob` preprocessor generates the matching `readParams`, which matches parameter names to Java fields, so a class declares its parameters once and gets a loader for free.

This is how the default structure defines about 20 raster views:

- `VanishingView`, `RowColView`, `TreeView`, `ManyToManyView`, `ParallelTextView`
- `CompassView`, `CursorView`, `ICView`, `CombinedView`, `MultiView`
- `SimpleTextView`, `Mind.Sun`
- cell-rendering factories such as `CellFlobFactory1` with `bg`, `ball`, `font` and `enlargefont`

Changing a cell's text or parameters changes the view with no recompile.

## 3. Executable code in cells

- **Command cells:** `ZZCommand.getCommand` turns a cell into a command if it reads as a ZOb. `ZZPrimitiveCommand` holds a `code` cell.
- **Text commands:** otherwise the cell text is parsed as a primitive action, with the verb first and arguments after, such as `CNCT X+`, `VSTRMCRSR -` or `RASTER +`.
- **Module commands:** `Module.ACTION` dispatches to a Java module, as with `XML.IMPORT`, `Notemap.NEW` or `Dumper.Write`.
- **Interpreted programs:** a root clone with a `d.xeq` neighbor is run by the Flowing Clang interpreter, so scripts are stored as cell structures.

## 4. Key bindings as a state machine

Bindings are parameter lists too. The parameter name is the chord string (`Ctrl-A`, `Shift-Left`, `MouseClicked1`), with special names `INSERT`, `DEFAULT` and `EDITBINDS`. The value is a command cell. The default structure has modes named "Normal mode", "Edit mode", "Cursel mode" and "Text edit mode".

- A window's current mode is a cursor on `d.bind`.
- A binding cell with a `d.3` head becomes the next mode, so transitions are data. Tab and Esc go back to a mode through the third argument of `addAct`.
- Lookup order in `perf()` is the view's `databindings`, then the applitude bindings, then the control view, then the current mode, then `INSERT`, then `DEFAULT`, then edit bindings.
- Views pick their variants by intersecting `d.1` with `d.clone` on the current mode.
- Esc with no binding calls `undo()`.

## 5. Windows and views described declaratively

- `Windows` on the system list, then `d.1`, then a `d.2` rank of frames. Each frame's text is the title.
- Under each frame, `d.bounds` holds four integer cells and `d.color` holds a background and foreground.
- A canvas cell's `d.1` neighbor is the view cell.
- A view cell carries its parameters on `d.2` (`View`, `CellView`, `ShowCursColor`, `CursorRecovery`), its displayed dimensions on `d.dims`, its selection on `d.mark`, and its cursor as cargo.
- `ZZWindows` observes all of it and rebuilds the frames on change. Closing a window excises the frame cell from `d.2`.
- Two default views, control and data, are paired with `d.ctrlview` and share system cursors with distinct colors.

## 6. User-extensible menus and lists

- **Actions:** `Actions` is a menu. Each `d.2` row is a command, and extra cells along `d.1` are alternatives.
- **Views and cell views:** `AllViews`, `Views`, `AllCellViews` and `CellViews` are long and short lists. The short lists hold clones of the long ones, which the code comments say makes it easy to clone and delete views.
- **Dimension lists:** `DimLists` holds ring-shaped lists of dimension names, and `SETDIMS` applies one to a view.
- **Customizing:** the user customizes by cloning cells and editing the clone, with the same operations used on any other data.

## 7. Interpreter and session state in cells

- **`NextAction`:** the pending first half of a two-key command, as an action ID or a dimension and direction.
- **`Input`:** the typed-input buffer, read and written by `getInbuf` and `appendInbuf`.
- **`Scrolls`:** the mapping from space to scroll IDs, via `findScrollCell`. A comment says it "MUST BE SAVED BETWEEN RESTARTS".
- **`SysCursors`:** the list of system cursors.
- **`OldSysList`:** `create()` preserves a previous system list here.
- **Other:** `GETSPACEID` and `SETSPACEID` actions, and `version:list` and `version:home` as part dimensions.

## Caveats

I haven't seen `ApplitudeMgr`, the Flowing Clang code, the `Modules/` directory or any actual data. Applitudes look like a layer that switches binding sets by which app the user clicked, but that is inference from `appbindings` and `APPLITUDE +/-`. I also don't know the file format that stores this, so the exact parameter shapes for modules like `Notemap` or `Prez` are unverified.

## Prompt:
Attached are sample data files from the "Adam's Royals" demonstration from Ted Nelson's website.  What can you infer about the file structures given the source code you have available?

## Response:
These files are a journaling store with one file per dimension plus a text file. I decoded the binary format and replayed all 13 files into a coherent structure. The only code I have is the in-memory side, so everything about the format comes from the bytes. I also can't confirm that the original storage code parses them the way I do.

## File layout

- **One file per dimension.** Each is named exactly after its dimension (`d.1`, `d.cursor-cargo` and so on).
- **`CONTENT`** holds cell text.
- **No `d.cellcreation` file.** That matches `IDDimension` being computed from the IDs.
- **`d.xeq` is a bare header.** The dimension exists but nothing is connected on it, so this space has no stored Flowing Clang scripts.

## Binary format

| Piece | Layout |
|---|---|
| Header (16 bytes) | `GZZ0` magic, an 8-byte big-endian number (42 in dimension files, 43 in `CONTENT`), then a 4-byte zero. I don't know what the number or the zero mean. |
| Block | `t`, a 4-byte stamp, a 4-byte payload length, then operations |
| `c` (dimension files) | two strings a, b: connect a to b, with b as a's positive neighbor |
| `d+` or `d-` (dimension files) | one string a: disconnect a's positive or negative link |
| `s` (`CONTENT`) | two strings, id and text: set the cell's text |

- **Strings** are a 2-byte length followed by UTF-8, which looks like Java's `DataOutputStream.writeUTF`.
- **Block lengths:** every block length matched its contents exactly, in all 13 files.
- **Cells** are decimal ID strings, and `1` is the home cell with text "HOME", as `getHomeCellID()` returns.
- **Links** are stored only as forward connections, the same as `ZZLocalDimension`'s `cp` table. The reverse map is rebuilt on load.

## A journal, not a snapshot

- **Append-only.** The first block (stamp 2) is a full dump of 587 cell texts and 316 `d.1` links. Later blocks are small deltas.
- **Global stamps.** Stamps are numbered across all files. A dimension file only has blocks for stamps where that dimension changed. `CONTENT` has every stamp from 2 to 51. This fits `ZZSpace`'s `stamp`, `undo`, `redo` and `commit` hooks, with undo meaning "back to an earlier stamp", though that is a guess.
- **Save markers.** Most even stamps in `CONTENT` contain a single `savetime` record in epoch milliseconds. The early ones decode to February and March 2004, and the last one to July 2026, so someone reopened and saved this demo recently.
- **Reserved keys.** `nextfreeid` is 985 and the highest cell ID used is 984. That matches `ZZDimSpace`'s `nextID` counter and its protected `setNextID`.
- **Block order.** Operations inside a block run in descending-ID order, like iterating a Java `Hashtable`, so they are not chronological.

## What the content shows

- **System list.** Walking `d.system` from home gives exactly the names the code looks up: `Views`, `CellViews`, `AllCellViews`, `DimLists`, `Bindings`, `EditBindings`, `Input`, `ClientCell`, `SysCursors`, `Applitudes`, `Windows` and `NextAction`. `Actions` and `AllViews` appear only on `d.2`, as `create()` does it.
- **`d.masterdim`.** It lists 33 dimensions, newest first, because `updateMasterDimList` inserts directly after home.
- **App-specific dimensions.** `d.children`, `d.marriage`, `d.date`, `d.cut` and `d.foo` show up there. The first three look like the genealogy dimensions.
- **Space version.** `d.gzz-space-version` links home to a cell with text "2", which I read as the space format version.
- **Persisted cursors.** Stamp 3 stores the text `-5285376` on two cells. That is `0xFFAF5A00`, which matches `new Color(0xaf5a00)` in `ZZKeyBindings1.getMode`. Cursor movement is saved like any other edit, which is why the `d.cursor*` files change at nearly every stamp.
- **The royals.**
  - Stamps 7 to 13 add people and titles, and stamp 15 adds years.
  - The data is a column of 80 names on `d.2`, roughly alphabetical with a few out of order (for example "Frederik VIII" before "Frederik IX").
  - Each name starts a `d.1` row: "Albert I" then "Prince of Monaco", "Alfonso XIII" then "King of Spain". Some rows are name-only.
  - Some names repeat as separate cells, such as two "Alice" cells. Cells are identities, not strings.

## Gaps

- **Missing dimension files.** `d.children`, `d.marriage` and `d.date` are registered in the master list but have no files in your upload. Of 45 year cells, only 18 are linked in the dimensions you sent. The family relationships are probably in those missing files, so I can't reconstruct the genealogy from this set. The other registered dimensions without files are `d.clone`, `d.color`, `d.bounds`, `d.mark`, `d.mark-set`, `d.bind`, `d.cellview`, `d.ctrlview`, `d..cursor-trigger`, `d.cut`, `d.foo` and the two `version:` entries. They may be unwritten, or you may have sent a subset.
- **Part dimensions.** I can't tell how a name containing `:` such as `version:list` maps to a filename.
- **`ZZTraverseCB`.** This is not its format, since it's a journal and not a visitor stream. That makes me think the interface is for import and export or other formats.

I have a small Python parser and replayer for this format. If you send the missing `d.*` files, I can finish the genealogy and export it as readable text.

## Prompt:
Please create a Python script that uses the information above to read an input "dimension" file and output a text file that gives human readable explanations of the data in that file.

## Response:
I'll write the script, then test it against your sample files, including corrupted input.

The first report reads well. I'm making three fixes before testing further: wrap long rank lines, tidy the extra-notes section, and add a caveat about the "detached" wording.

`gzz_explain.py` reads one dimension file (or `CONTENT`) and writes a plain-English text report. It uses only the Python 3.8+ standard library.

```
python gzz_explain.py d.2                       # writes d.2.explained.txt
python gzz_explain.py d.cursor -o report.txt
python gzz_explain.py d.1 --content /path/to/CONTENT --full
python gzz_explain.py d.2 -o -                  # print to screen
```

If a `CONTENT` file sits next to the input, cells appear as `#893 "Albert"` instead of `#893`. Use `--no-content` to turn that off.

Each report has these parts:

1. **What the file is.** Size, header, block and operation counts, and a plain-language note on what that dimension is for. The notes come from the glossary I built from the Java source.
2. **History.** One entry per stamp, with each operation described in words, such as `Link #60 "Normal mode" → #329 "q"`. It also notes when a link displaced an old neighbour and gives the first recorded save date at or after that stamp.
3. **Current state.** The file replayed into ranks (chains or loops), with counts, a rank-length summary, and a consistency check. Long ranks wrap and abbreviate.
4. **Reading notes** for a few dimensions. These cover the `d.masterdim` and `d.system` name lists, `d.cursor` accursed-to-cursor pairs, and short explanations for `d.cursor-list`, `d.cursor-cargo` and `d.gzz-space-version`.
5. **For `CONTENT`**, a text listing, the save-time markers, the next free ID, and cells whose text changed over time.

I ran it on all 13 sample files. Corrupt input is handled: an empty file, a non-journal file, a truncated file, an unknown operation byte and trailing garbage each give a clear message. For damaged files it still reports everything it could read, and it flags the damaged block.

The format is reverse-engineered, so the report ends with a short section of caveats.
- **Unknown header:** the 8-byte and 4-byte header values (42 and 0 in the samples) are shown but not interpreted.
- **Unrecognised dimensions:** names not in the glossary are marked as probably application-specific.
- **Replay order:** inside a block the script applies disconnects before connects. For all 12 sample dimension files, every ordering I tried gave identical final links, so the choice doesn't matter for that data.
- **Detached notes:** a note like "old neighbour was detached" describes one replay step. The cell is often re-linked later in the same block, which is how an insertion into a rank looks.

## Response:
> **Artifact: gzz_explain**
```python
#!/usr/bin/env python3
"""
gzz_explain.py - explain a GZigZag "GZZ0" dimension file in plain English.

GZigZag (the ZigZag implementation behind demos such as "Adam's Royals")
stores a space as a folder of append-only journal files:

    d.1, d.2, d.cursor, d.masterdim, ...   one file per dimension
    CONTENT                                 the text of every cell

This script reads ONE such file and writes a human-readable text report:
what the file is, how it changed over time, and what its final state is
(the ranks of linked cells).  If a CONTENT file sits next to the input (or
is given with --content), cell IDs are shown together with their text.

File format, as inferred from the sample data and the GZigZag Java sources
(there is no official specification; see the notes at the end of each report):

    header   "GZZ0", 8-byte big-endian number, 4-byte number        (16 bytes)
    block    't', u32 stamp, u32 payload length, <operations>
    ops      'c'  <utf> a <utf> b     connect a -> b  (b is a's + neighbour)
             'd+' <utf> a             disconnect a from its + neighbour
             'd-' <utf> a             disconnect a from its - neighbour
             's'  <utf> id <utf> txt  set the text of cell id        (CONTENT)
    <utf>    u16 big-endian length + modified UTF-8 (Java writeUTF)

Usage:
    python gzz_explain.py d.2
    python gzz_explain.py d.cursor -o cursor_report.txt
    python gzz_explain.py d.1 --content /path/to/CONTENT --full
    python gzz_explain.py CONTENT

Requires only the Python 3.8+ standard library.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import json
import os
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

MAGIC = b"GZZ0"
HEADER_SIZE = 16
WIDTH = 100

# --------------------------------------------------------------------------
# Glossary of dimension names.  Inferred from how the Java code uses them;
# nothing here is documented by the original authors.
# --------------------------------------------------------------------------
GLOSSARY: Dict[str, str] = {
    "d.1": "General-purpose dimension. By convention it carries values: the "
           "cells after a parameter name, or the rest of a 'row'.",
    "d.2": "General-purpose dimension. By convention the 'next item' / list "
           "dimension: property lists, menus and name lists run along it.",
    "d.3": "General-purpose dimension. By convention it links to a "
           "sub-structure; parameter lookup follows it to inherit values.",
    "d.clone": "Clone chains. Cells in one rank share the text of the rank's "
               "first cell (the 'root clone').",
    "d.cellcreation": "Creation order of cells. Not stored on disk; computed "
                      "from the numeric cell IDs.",
    "d.masterdim": "Registry of every dimension in the space. Each cell's "
                   "text is a dimension name; ranks run from the home cell.",
    "d.system": "System list hanging off the home cell: named cells such as "
                "Views, Bindings, Windows and ClientCell used by the program.",
    "d.cursor": "Links an 'accursed' cell (the one pointed at) to the cursor "
                "cell that points at it.",
    "d.cursor-list": "Chains several cursor cells that point at the same "
                     "accursed cell.",
    "d.cursor-cargo": "Attaches 'cargo' cells (typically windows/views) "
                      "behind a cursor cell; the cargo follows that cursor. "
                      "The cursor cell's text holds the text offset.",
    "d..cursor-trigger": "Links a cargo cell to a command cell that runs "
                         "when the cursor moves.",
    "d.view": "Chains the view (window) cells under the ClientCell.",
    "d.ctrlview": "Pairs a control view with the data view it controls.",
    "d.dims": "A view's list of dimensions to display (entries are pointers "
              "to cells whose text is a dimension name).",
    "d.mark": "A view's marked cells: relation cells chained here point at "
              "the marked cells via d.mark-set.",
    "d.mark-set": "Points from a mark relation cell to the marked cell.",
    "d.bind": "A window's current key-bindings mode (a cursor on a bindings "
              "cell).",
    "d.cellview": "Selects a per-cell display/edit-bindings override.",
    "d.xeq": "Flag dimension: a code cell with a d.xeq neighbour is run by "
             "the Flowing Clang interpreter instead of as a plain command.",
    "d.bounds": "A window's position and size as four number cells.",
    "d.color": "Colours for windows or modes, stored as cell text.",
    "d.photo": "URL of an image shown by the photo view.",
    "d.help": "Help text attached to a view cursor.",
    "d.slices": "Chains the home cells of slices (sub-spaces).",
    "d.gzz-space-version": "Links the home cell to a cell whose text is the "
                           "space-format version number.",
    "d.children": "Application-specific (meaning inferred from the name "
                  "only): parent-to-child relations.",
    "d.marriage": "Application-specific (meaning inferred from the name "
                  "only): marriage relations.",
    "d.date": "Application-specific (meaning inferred from the name only): "
              "links a cell to a date or year.",
}


class FormatError(Exception):
    """The file is not a readable GZZ0 journal."""


class Truncated(FormatError):
    pass


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
@dataclass
class Op:
    kind: str                 # 'c', 'd+', 'd-', 's'
    a: str
    b: Optional[str] = None


@dataclass
class Block:
    stamp: int
    length: int
    offset: int
    ops: List[Op] = field(default_factory=list)
    damaged: bool = False


@dataclass
class Journal:
    path: str
    size: int
    tag: int
    reserved: int
    blocks: List[Block] = field(default_factory=list)
    error: Optional[str] = None


def decode_utf(raw: bytes) -> str:
    """Decode Java 'modified UTF-8' (as written by DataOutputStream.writeUTF)."""
    raw = raw.replace(b"\xc0\x80", b"\x00")
    try:
        s = raw.decode("utf-8", "surrogatepass")
        return s.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        return raw.decode("utf-8", "replace")


class Reader:
    def __init__(self, data: bytes, pos: int, end: int):
        self.data, self.pos, self.end = data, pos, end

    def take(self, n: int) -> bytes:
        if self.pos + n > self.end:
            raise Truncated(f"data ends unexpectedly at byte offset {self.pos}")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def u8(self) -> int:
        return self.take(1)[0]

    def utf(self) -> str:
        n = struct.unpack(">H", self.take(2))[0]
        return decode_utf(self.take(n))


def parse_journal(path: str) -> Journal:
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < HEADER_SIZE:
        raise FormatError(f"file is only {len(data)} bytes; a GZZ0 header "
                          f"needs {HEADER_SIZE}")
    if data[:4] != MAGIC:
        raise FormatError(f"missing 'GZZ0' signature (file starts with "
                          f"{data[:4]!r}); this is not a GZigZag journal")
    tag, reserved = struct.unpack(">QI", data[4:HEADER_SIZE])
    j = Journal(path, len(data), tag, reserved)
    pos = HEADER_SIZE
    while pos < len(data):
        if data[pos:pos + 1] != b"t":
            j.error = (f"expected a block marker 't' at byte offset {pos} but "
                       f"found 0x{data[pos]:02x}; reading stopped there")
            break
        if pos + 9 > len(data):
            j.error = f"truncated block header at byte offset {pos}"
            break
        stamp, length = struct.unpack(">II", data[pos + 1:pos + 9])
        body, end = pos + 9, pos + 9 + length
        blk = Block(stamp, length, pos)
        if end > len(data):
            blk.damaged = True
            j.error = (f"block for stamp {stamp} claims {length} bytes but only "
                       f"{len(data) - body} remain (file truncated?)")
            end = len(data)
        r = Reader(data, body, end)
        try:
            while r.pos < r.end:
                code = chr(r.u8())
                if code == "c":
                    blk.ops.append(Op("c", r.utf(), r.utf()))
                elif code == "d":
                    sign = chr(r.u8())
                    if sign not in "+-":
                        raise FormatError(f"bad disconnect direction {sign!r} "
                                          f"at byte offset {r.pos - 1}")
                    blk.ops.append(Op("d" + sign, r.utf()))
                elif code == "s":
                    blk.ops.append(Op("s", r.utf(), r.utf()))
                else:
                    raise FormatError(f"unknown operation byte {code!r} at "
                                      f"byte offset {r.pos - 1}")
        except FormatError as e:
            blk.damaged = True
            j.error = f"in the block for stamp {stamp}: {e}"
        j.blocks.append(blk)
        if j.error:
            break
        pos = end
    return j


# --------------------------------------------------------------------------
# Link state (mirrors ZZLocalDimension: forward map + backward map)
# --------------------------------------------------------------------------
class Links:
    def __init__(self) -> None:
        self.cp: Dict[str, str] = {}      # cell -> its + neighbour
        self.cm: Dict[str, str] = {}      # cell -> its - neighbour

    def disconnect(self, c: str, direction: int) -> Optional[str]:
        if direction > 0:
            other = self.cp.pop(c, None)
            if other is not None:
                self.cm.pop(other, None)
        else:
            other = self.cm.pop(c, None)
            if other is not None:
                self.cp.pop(other, None)
        return other

    def connect(self, a: str, b: str):
        """Returns None if already connected, else (old_next, old_prev)."""
        if self.cp.get(a) == b:
            return None
        old_next = self.disconnect(a, 1)
        old_prev = self.disconnect(b, -1)
        self.cp[a], self.cm[b] = b, a
        return old_next, old_prev

    def consistent(self) -> bool:
        return (all(self.cm.get(b) == a for a, b in self.cp.items())
                and all(self.cp.get(a) == b for b, a in self.cm.items()))


def sort_key(cid: str):
    return (0, int(cid), "") if cid.isdigit() else (1, 0, cid)


def build_ranks(links: Links) -> List[Tuple[List[str], bool]]:
    """Split the links into ranks. Returns (cells, is_circular) pairs."""
    cells = set(links.cp) | set(links.cm) | set(links.cp.values()) \
        | set(links.cm.values())
    seen: set = set()
    ranks: List[Tuple[List[str], bool]] = []
    for head in sorted((c for c in cells if c in links.cp and c not in links.cm),
                       key=sort_key):
        chain, cur = [head], head
        seen.add(head)
        while cur in links.cp and links.cp[cur] not in seen:
            cur = links.cp[cur]
            chain.append(cur)
            seen.add(cur)
        ranks.append((chain, False))
    for start in sorted(cells - seen, key=sort_key):
        if start in seen:
            continue
        members, cur = [start], start
        seen.add(start)
        while cur in links.cp and links.cp[cur] not in seen:
            cur = links.cp[cur]
            members.append(cur)
            seen.add(cur)
        # The Java code names the lexically greatest ID the head of a loop.
        i = members.index(max(members))
        ranks.append((members[i:] + members[:i], True))
    return ranks


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def quote(text: str, width: int) -> str:
    s = json.dumps(text, ensure_ascii=False)
    return s if len(s) <= width else s[:width - 2] + "…\""


def fmt_ms(ms) -> str:
    try:
        d = dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc)
        return d.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OverflowError, OSError):
        return f"(invalid time {ms})"


def make_label(texts: Optional[Dict[str, str]], width: int) -> Callable[[str], str]:
    def label(cid: str) -> str:
        if texts is None:
            return f"#{cid}"
        t = texts.get(cid, "")
        return f"#{cid} {quote(t, width)}" if t != "" else f"#{cid} (empty)"
    return label


def rank_text(chain: List[str], circular: bool, label, max_cells: int) -> str:
    if len(chain) > max_cells:
        keep_end = 3
        keep_start = max_cells - keep_end
        parts = [label(c) for c in chain[:keep_start]]
        parts.append(f"… {len(chain) - max_cells} more cells …")
        parts += [label(c) for c in chain[-keep_end:]]
    else:
        parts = [label(c) for c in chain]
    s = "  →  ".join(parts)
    return s + "  →  (back to the start)" if circular else s


class Out:
    def __init__(self) -> None:
        self.lines: List[str] = []

    def add(self, text: str = "") -> None:
        self.lines.append(text)

    def head(self, title: str) -> None:
        self.add()
        self.add("=" * WIDTH)
        self.add(title)
        self.add("=" * WIDTH)

    def para(self, text: str, indent: int = 0) -> None:
        import textwrap
        for line in textwrap.wrap(text, WIDTH - indent) or [""]:
            self.add(" " * indent + line)

    def bullet(self, text: str, indent: int = 2) -> None:
        import textwrap
        wrapped = textwrap.wrap(text, WIDTH - indent - 2)
        for i, line in enumerate(wrapped or [""]):
            self.add(" " * indent + ("- " if i == 0 else "  ") + line)


# --------------------------------------------------------------------------
# Content file (cell texts)
# --------------------------------------------------------------------------
@dataclass
class Content:
    path: str
    texts: Dict[str, str]
    saves: List[Tuple[int, int]]          # (stamp, epoch ms)


def load_content(path: str) -> Content:
    j = parse_journal(path)
    texts: Dict[str, str] = {}
    saves: List[Tuple[int, int]] = []
    for blk in j.blocks:
        for op in blk.ops:
            if op.kind == "s":
                texts[op.a] = op.b or ""
                if op.a == "savetime" and (op.b or "").isdigit():
                    saves.append((blk.stamp, int(op.b)))
    return Content(path, texts, saves)


def save_time_after(content: Optional[Content], stamp: int) -> Optional[int]:
    """The first recorded save time at or after the given stamp."""
    if not content or not content.saves:
        return None
    stamps = [s for s, _ in content.saves]
    i = bisect.bisect_left(stamps, stamp)
    return content.saves[i][1] if i < len(content.saves) else None


# --------------------------------------------------------------------------
# Report sections
# --------------------------------------------------------------------------
def describe_dimension(name: str) -> str:
    if name in GLOSSARY:
        return GLOSSARY[name]
    if ":" in name:
        return ("A dimension provided by a 'space part' (the prefix before the "
                "colon names the part), i.e. a virtual region of the space.")
    return ("Not a dimension this script recognises; it is probably "
            "application-specific. What it means depends on how the data uses it.")


def detect_kind(j: Journal, name: str) -> str:
    kinds = {("text" if op.kind == "s" else "links")
             for b in j.blocks for op in b.ops}
    if kinds == {"text"}:
        return "content"
    if kinds == {"links"}:
        return "dimension"
    if not kinds:
        return "dimension" if name.startswith("d.") else "content"
    return "mixed"


def section_overview(out: Out, j: Journal, name: str, kind: str,
                     content: Optional[Content]) -> None:
    out.head("1. WHAT THIS FILE IS")
    out.add(f"File        : {j.path}")
    out.add(f"Size        : {j.size} bytes")
    out.add(f"Signature   : GZZ0 (GZigZag journal)")
    out.add(f"Header      : format tag {j.tag}, reserved value {j.reserved}  "
            f"(meaning unknown; the sample files use 42 for dimension files "
            f"and 43 for CONTENT)")
    ops = Counter(op.kind for b in j.blocks for op in b.ops)
    stamps = [b.stamp for b in j.blocks]
    out.add(f"Blocks      : {len(j.blocks)}"
            + (f"  (stamps {stamps[0]} to {stamps[-1]})" if stamps else ""))
    if ops:
        names = {"c": "connect", "d+": "disconnect(+)", "d-": "disconnect(-)",
                 "s": "set-text"}
        out.add("Operations  : " + ", ".join(
            f"{names[k]}={ops[k]}" for k in ("c", "d+", "d-", "s") if ops[k]))
    out.add()
    if kind == "content":
        out.para("This is the CONTENT file. It does not store links; it stores "
                 "the text of the cells (and a few bookkeeping values) as "
                 "'set text' records, one block per timestamp.")
    elif kind == "dimension":
        out.para(f"This file stores the dimension '{name}'. A dimension "
                 "arranges cells into ranks: each cell has at most one neighbour "
                 "in the positive (+) direction and one in the negative (-) "
                 "direction, so cells form chains (or loops). The file is an "
                 "append-only journal of 'connect' and 'disconnect' records; "
                 "replaying it from the top gives the current links.")
        out.add()
        out.add(f"What '{name}' is for:")
        out.para(describe_dimension(name), 2)
        if content:
            out.add()
            out.para(f"Cell texts come from {content.path} ({len(content.texts)} "
                     "records), so cells are shown as  #ID \"text\".", 0)
        else:
            out.add()
            out.para("No CONTENT file was used, so cells are shown only by ID "
                     "(#329). Put the dimension file next to its CONTENT file, "
                     "or pass --content, to see the cell texts.")
    else:
        out.para("This file contains both link and text records, which is "
                 "unusual; both are explained below.")
    if j.error:
        out.add()
        out.para("WARNING - the file could not be read to the end: " + j.error
                 + ". Everything before that point is reported below.")


def section_timeline(out: Out, j: Journal, kind: str, label, content,
                     max_ops: int) -> Tuple[Links, Dict[str, str]]:
    out.head("2. HISTORY (one block per timestamp, in file order)")
    out.para("Each block is one saved change set, tagged with a stamp number. "
             "The stamp is shared by all files of a space, so the same stamp "
             "in different files belongs to the same user action. The first "
             "block of a file normally holds the whole initial state; later "
             "blocks are small incremental changes.")
    out.add()
    if not j.blocks:
        out.add("(no blocks: nothing was ever stored in this file)")
        return Links(), {}
    links = Links()
    texts: Dict[str, str] = {}
    for blk in j.blocks:
        lines: List[str] = []
        n = Counter()
        ordered = ([o for o in blk.ops if o.kind in ("d+", "d-")]
                   + [o for o in blk.ops if o.kind == "c"]
                   + [o for o in blk.ops if o.kind == "s"])
        for op in ordered:
            if op.kind in ("d+", "d-"):
                d = 1 if op.kind == "d+" else -1
                sign = "+" if d > 0 else "-"
                old = links.disconnect(op.a, d)
                if old is None:
                    lines.append(f"Unlink {label(op.a)}: it had no {sign} "
                                 f"neighbour, so nothing changed")
                    n["noop"] += 1
                else:
                    lines.append(f"Unlink {label(op.a)} from its {sign} "
                                 f"neighbour {label(old)}")
                    n["unlink"] += 1
            elif op.kind == "c":
                res = links.connect(op.a, op.b)
                if res is None:
                    lines.append(f"Link {label(op.a)}  →  {label(op.b)} "
                                 f"(already linked, no change)")
                    n["noop"] += 1
                else:
                    old_next, old_prev = res
                    extra = []
                    if old_next is not None:
                        extra.append(f"its old + neighbour {label(old_next)} "
                                     f"was detached")
                    if old_prev is not None:
                        extra.append(f"{label(op.b)}'s old - neighbour "
                                     f"{label(old_prev)} was detached")
                    lines.append(f"Link {label(op.a)}  →  {label(op.b)}"
                                 + (f"   ({'; '.join(extra)})" if extra else ""))
                    n["link"] += 1
            else:  # 's'
                old = texts.get(op.a)
                texts[op.a] = op.b or ""
                if op.a == "savetime":
                    lines.append(f"Save time recorded: {fmt_ms(op.b)}")
                    n["meta"] += 1
                elif op.a == "nextfreeid":
                    lines.append(f"Next free cell ID is now {op.b}"
                                 + (f" (was {old})" if old else ""))
                    n["meta"] += 1
                elif old is None:
                    lines.append(f"Set text of #{op.a} to {quote(op.b or '', 60)}")
                    n["text"] += 1
                else:
                    lines.append(f"Change text of #{op.a} from "
                                 f"{quote(old, 40)} to {quote(op.b or '', 40)}")
                    n["text"] += 1
        summary = ", ".join(f"{v} {k}" for k, v in n.items()) or "empty"
        when = save_time_after(content, blk.stamp)
        out.add(f"Stamp {blk.stamp}  -  {len(blk.ops)} operation(s): {summary}"
                + ("   [DAMAGED BLOCK]" if blk.damaged else ""))
        if when is not None and kind == "dimension":
            out.add(f"   first save recorded at or after this stamp: "
                    f"{fmt_ms(when)}")
        for line in lines[:max_ops]:
            out.add("   " + line)
        if len(lines) > max_ops:
            out.add(f"   … and {len(lines) - max_ops} more (use --full to "
                    f"list every operation)")
        out.add()
    return links, texts


def section_state(out: Out, links: Links, name: str, label, max_ranks: int,
                  max_cells: int, have_text: bool) -> List[Tuple[List[str], bool]]:
    out.head(f"3. CURRENT STATE OF '{name}' (after replaying every block)")
    if not links.cp and not links.cm:
        out.para("No cell is linked on this dimension. The dimension exists "
                 "(it is registered in the space) but holds no connections.")
        return []
    ranks = build_ranks(links)
    cells = len(set(links.cp) | set(links.cm))
    lin = sum(1 for _, c in ranks if not c)
    loops = len(ranks) - lin
    out.add(f"Linked cells  : {cells}")
    out.add(f"Ranks         : {len(ranks)}  ({lin} linear, {loops} circular)")
    out.add(f"Link records  : {len(links.cp)} (each is one 'A → B' link)")
    out.add(f"Consistent    : "
            f"{'yes' if links.consistent() else 'NO - forward/backward links disagree'}")
    hist = Counter(len(ch) for ch, _ in ranks)
    out.add("Rank lengths : " + ", ".join(
        f"{n} rank(s) of {l} cells" for l, n in sorted(hist.items())[:12])
        + (" …" if len(hist) > 12 else ""))
    out.add()
    out.para("A rank is a chain of cells; '→' points in the positive (+) "
             "direction. Ranks are listed longest first.")
    out.add()
    order = sorted(ranks, key=lambda r: (-len(r[0]), sort_key(r[0][0])))
    for i, (chain, circ) in enumerate(order[:max_ranks], 1):
        out.add(f"Rank {i} ({len(chain)} cells{', circular' if circ else ''}):")
        out.add("   " + rank_text(chain, circ, label, max_cells))
    if len(order) > max_ranks:
        out.add()
        out.add(f"… {len(order) - max_ranks} more rank(s) not shown "
                f"(use --max-ranks N or --full)")
    return ranks


def section_special(out: Out, name: str, links: Links, ranks, label,
                    have_text: bool) -> None:
    notes: List[str] = []
    home_rank = next((ch for ch, _ in ranks if "1" in ch), None)
    if name in ("d.masterdim", "d.system") and home_rank:
        what = ("dimensions registered in this space" if name == "d.masterdim"
                else "system-list entries")
        notes.append(f"The rank through the home cell (#1) lists the {what}, "
                     f"in rank order:")
        for i, c in enumerate(home_rank, 1):
            notes.append(f"   {i:>3}. {label(c)}")
        if not have_text:
            notes.append("   (cell names need the CONTENT file)")
    elif name == "d.cursor":
        notes.append("Each rank reads: accursed cell (the one pointed at), "
                     "then the cursor cell that points at it:")
        for ch, _ in ranks[:40]:
            notes.append(f"   {label(ch[0])}   ←  pointed at by cursor "
                         + ", ".join(label(c) for c in ch[1:]))
        if len(ranks) > 40:
            notes.append(f"   … {len(ranks) - 40} more")
    elif name == "d.cursor-list":
        notes.append("Each rank is a group of cursor cells that point at the "
                     "same cell (the first is the one connected on d.cursor).")
    elif name == "d.cursor-cargo":
        notes.append("In each rank the first cell is a cursor cell and the "
                     "cells after it are its cargo (e.g. windows that follow "
                     "that cursor).")
    elif name == "d.gzz-space-version" and links.cp:
        a, b = next(iter(links.cp.items()))
        notes.append(f"{label(a)} is linked to {label(b)}; the text of the "
                     f"second cell is the space format version.")
    if notes:
        out.head(f"4. EXTRA READING NOTES FOR '{name}'")
        for n in notes:
            out.add(n if n.startswith("   ") else "")
            if not n.startswith("   "):
                out.para(n)


def section_content(out: Out, j: Journal, texts: Dict[str, str],
                    max_texts: int, width: int) -> None:
    out.head("3. CURRENT STATE OF CELL TEXT (after replaying every block)")
    cells = {k: v for k, v in texts.items() if k.isdigit()}
    meta = {k: v for k, v in texts.items() if not k.isdigit()}
    out.add(f"Cells with a stored text : {len(cells)}")
    empty = sum(1 for v in cells.values() if v == "")
    out.add(f"   of which empty text   : {empty}")
    if "nextfreeid" in meta:
        out.add(f"Next free cell ID        : {meta['nextfreeid']}  "
                f"(so IDs up to {int(meta['nextfreeid']) - 1} have been "
                f"allocated; cells with no record have empty text)"
                if meta["nextfreeid"].isdigit()
                else f"Next free cell ID        : {meta['nextfreeid']}")
    saves = [(b.stamp, op.b) for b in j.blocks for op in b.ops
             if op.kind == "s" and op.a == "savetime"]
    if saves:
        out.add(f"Save markers             : {len(saves)}  "
                f"(first {fmt_ms(saves[0][1])}, last {fmt_ms(saves[-1][1])})")
    other = [k for k in meta if k not in ("savetime", "nextfreeid")]
    if other:
        out.add("Other bookkeeping keys   : " + ", ".join(sorted(other)))
    out.add()
    out.add(f"Cell texts, by ID (first {max_texts}):")
    shown = sorted(cells, key=sort_key)[:max_texts]
    for cid in shown:
        out.add(f"   #{cid:<6} {quote(cells[cid], width)}")
    if len(cells) > len(shown):
        out.add(f"   … {len(cells) - len(shown)} more (use --max-texts N or --full)")
    history: Dict[str, List[Tuple[int, str]]] = {}
    for b in j.blocks:
        for op in b.ops:
            if op.kind == "s" and op.a.isdigit():
                history.setdefault(op.a, []).append((b.stamp, op.b or ""))
    changed = {k: h for k, h in history.items()
               if len({v for _, v in h}) > 1}
    if changed:
        out.add()
        out.add(f"Cells whose text changed over time ({len(changed)}):")
        for cid in sorted(changed, key=sort_key)[:15]:
            trail = "  →  ".join(f"{quote(v, 24)}@{s}" for s, v in changed[cid])
            out.add(f"   #{cid}: {trail}")
        if len(changed) > 15:
            out.add(f"   … {len(changed) - 15} more")


def section_notes(out: Out, kind: str) -> None:
    out.head("NOTES ON HOW TO TRUST THIS REPORT")
    notes = [
        "The file format is not documented. It was reverse-engineered from "
        "sample data and the GZigZag Java sources, then checked by replaying "
        "complete sample spaces without inconsistencies. Treat the "
        "explanations as well-founded inference, not specification.",
    ]
    if kind != "content":
        notes += [
            "Inside a block the records are stored in hash-table order, not in "
            "the order the user made them. This script applies the "
            "disconnections of a block first and its connections second.",
            "'Positive' (+) is the direction of 'A → B'. For a circular rank "
            "the start is the cell with the lexically greatest ID, which "
            "matches how the Java code picks a loop's 'head'.",
            "Dimension meanings come from how the Java code uses each name; "
            "application-specific dimensions are guessed from their names.",
            "Save times are matched to stamps heuristically: the first "
            "'savetime' record at or after a block's stamp.",
        ]
    for n in notes:
        out.bullet(n)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def build_report(args) -> str:
    j = parse_journal(args.input)
    name = args.name or os.path.basename(args.input)
    kind = detect_kind(j, name)

    content: Optional[Content] = None
    if kind != "content" and not args.no_content:
        cpath = args.content or os.path.join(
            os.path.dirname(os.path.abspath(args.input)), "CONTENT")
        if os.path.isfile(cpath):
            try:
                content = load_content(cpath)
            except (FormatError, OSError) as e:
                print(f"warning: could not use {cpath}: {e}", file=sys.stderr)
        elif args.content:
            print(f"warning: --content file {cpath} not found", file=sys.stderr)

    big = 10 ** 9
    max_ops = big if args.full else args.max_ops
    max_ranks = big if args.full else args.max_ranks
    max_cells = big if args.full else args.max_cells_per_rank
    max_texts = big if args.full else args.max_texts

    label = make_label(content.texts if content else None, args.text_width)

    out = Out()
    out.add("GZigZag file report")
    out.add("-" * WIDTH)
    section_overview(out, j, name, kind, content)
    links, texts = section_timeline(out, j, kind, label, content, max_ops)
    if kind in ("dimension", "mixed"):
        ranks = section_state(out, links, name, label, max_ranks, max_cells,
                              content is not None)
        section_special(out, name, links, ranks, label, content is not None)
    if kind in ("content", "mixed"):
        section_content(out, j, texts, max_texts, args.text_width)
    section_notes(out, kind)
    return "\n".join(out.lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Explain a GZigZag GZZ0 dimension (or CONTENT) file in "
                    "plain English.")
    ap.add_argument("input", help="dimension file such as d.1, d.cursor, "
                                  "d.masterdim (or CONTENT)")
    ap.add_argument("-o", "--output",
                    help="output text file (default: <input name>.explained.txt "
                         "in the current directory; '-' prints to the screen)")
    ap.add_argument("--content", help="path to the CONTENT file (default: the "
                                      "file called CONTENT next to the input)")
    ap.add_argument("--no-content", action="store_true",
                    help="do not look up cell texts; show bare cell IDs")
    ap.add_argument("--name", help="dimension name (default: the file name)")
    ap.add_argument("--full", action="store_true",
                    help="do not truncate any listing")
    ap.add_argument("--max-ops", type=int, default=12,
                    help="operations listed per block (default 12)")
    ap.add_argument("--max-ranks", type=int, default=30,
                    help="ranks listed in the current state (default 30)")
    ap.add_argument("--max-cells-per-rank", type=int, default=20,
                    help="cells shown per rank before abbreviating (default 20)")
    ap.add_argument("--max-texts", type=int, default=60,
                    help="cell texts listed for CONTENT (default 60)")
    ap.add_argument("--text-width", type=int, default=40,
                    help="maximum characters of a cell's text shown (default 40)")
    args = ap.parse_args(argv)

    try:
        report = build_report(args)
    except FormatError as e:
        print(f"error: {args.input}: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.output == "-":
        sys.stdout.write(report)
    else:
        path = args.output or (os.path.basename(args.input) + ".explained.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

