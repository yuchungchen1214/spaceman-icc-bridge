"""Use the release launcher's pre-Tahoe native appearance for Python runs."""
import sys


def configure_native_appearance():
    if sys.platform != 'darwin':
        return
    import ctypes
    ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
    runtime = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    runtime.objc_getClass.argtypes = [ctypes.c_char_p]
    runtime.objc_getClass.restype = ctypes.c_void_p
    runtime.sel_registerName.argtypes = [ctypes.c_char_p]
    runtime.sel_registerName.restype = ctypes.c_void_p
    selector = runtime.sel_registerName
    send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', runtime))
    string = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(('objc_msgSend', runtime))
    boolean = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(('objc_msgSend', runtime))
    set_value = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(('objc_msgSend', runtime))
    bundle = send(runtime.objc_getClass(b'NSBundle'), selector(b'mainBundle'))
    info = send(bundle, selector(b'infoDictionary'))
    key = string(runtime.objc_getClass(b'NSString'), selector(b'stringWithUTF8String:'), b'UIDesignRequiresCompatibility')
    value = boolean(runtime.objc_getClass(b'NSNumber'), selector(b'numberWithBool:'), True)
    if info:
        # Process-local only: no modification to Python or installed app plists.
        set_value(info, selector(b'setObject:forKey:'), value, key)
