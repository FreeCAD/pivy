/**************************************************************************\
 *
 *  This file is part of the Coin 3D visualization library.
 *  Copyright (C) 1998-2002 by Systems in Motion. All rights reserved.
 *
 *  This library is free software; you can redistribute it and/or
 *  modify it under the terms of the GNU Lesser General Public License
 *  version 2.1 as published by the Free Software Foundation. See the
 *  file LICENSE.LGPL at the root directory of the distribution for
 *  more details.
 *
 *  If you want to use Coin for applications not compatible with the
 *  LGPL, please contact SIM to acquire a Professional Edition license.
 *
 *  Systems in Motion, Prof Brochs gate 6, 7030 Trondheim, NORWAY
 *  http://www.sim.no support@sim.no Voice: +47 22114160 Fax: +47 22207097
 *
\**************************************************************************/

#ifndef COIN_SOFIELDCONTAINER_H
#define COIN_SOFIELDCONTAINER_H

#include <Inventor/misc/SoBase.h>

class SbString;
class SoFieldData;
class SoFieldList;
class SoOutput;

#ifdef __PIVY__
%rename(set_str_in) SoFieldContainer::set(const char * fielddata, SoInput * in);

%feature("shadow") SoFieldContainer::set(const char * const fielddata) %{
def set(*args):
   if len(args) == 3:
      return apply(pivyc.SoFieldContainer_set_str_in,args)
   return apply(pivyc.SoFieldContainer_set,args)
%}

%rename(get_str_out) SoFieldContainer::get(SbString & fielddata, SoOutput * out);

%feature("shadow") SoFieldContainer::get(SbString & fielddata) %{
def get(*args):
   if len(args) == 3:
      return apply(pivyc.SoFieldContainer_get_str_out,args)
   return apply(pivyc.SoFieldContainer_get,args)
%}

/**
 * ugly(tm) workaround for the getFieldName() method. the second argument
 * of this method is the actual return value of the method.
 * %apply SbName *OUTPUT { SbName & name }; did not work as
 * the typemap(in) SbName & specified in pivy.i has precedence
 * over any %apply rule applied to the same type. :(
 * so we have to live with this ugly duck solution until something better
 * is found...
 **/
%typemap(argout) SbName & getFieldName_name {
  PyObject *o, *o2, *o3;

  o = SWIG_NewPointerObj((void *) $1, SWIGTYPE_p_SbName, 1);

  if ((!$result) || ($result == Py_None)) {
	$result = o;
  } 
  else {
	if (!PyTuple_Check($result)) {
	  PyObject *o2 = $result;
	  $result = PyTuple_New(1);
	  PyTuple_SetItem($result,0,o2);
	}
	o3 = PyTuple_New(1);
	PyTuple_SetItem(o3,0,o);
	o2 = $result;
	$result = PySequence_Concat(o2,o3);
	Py_DECREF(o2);
	Py_DECREF(o3);
  }
}

%typemap(ignore) SbName & getFieldName_name (SbName *temp) {
    $1 = new SbName();
}

%apply SbString *OUTPUT { SbString & fielddata };
%apply SoFieldList *OUTPUT { SoFieldList & l };
%apply SoFieldList *INOUT { SoFieldList & l_inout };
#endif


class COIN_DLL_API SoFieldContainer : public SoBase {
  typedef SoBase inherited;

public:
  static void initClass(void);
  static SoType getClassTypeId(void);

  void setToDefaults(void);
  SbBool hasDefaultValues(void) const;

  SbBool fieldsAreEqual(const SoFieldContainer * container) const;
  void copyFieldValues(const SoFieldContainer * container,
                       SbBool copyconnections = FALSE);

  SbBool set(const char * const fielddata);
  void get(SbString & fielddata);

  virtual int getFields(SoFieldList & l) const;
  virtual int getAllFields(SoFieldList & l) const;
  virtual SoField * getField(const SbName & name) const;
  virtual SoField * getEventIn(const SbName & name) const;
  virtual SoField * getEventOut(const SbName & name) const;

#ifdef __PIVY__
  SbBool getFieldName(const SoField * const field, SbName & getFieldName_name) const;
#else
  SbBool getFieldName(const SoField * const field, SbName & name) const;
#endif

  SbBool enableNotify(const SbBool flag);
  SbBool isNotifyEnabled(void) const;

  SbBool set(const char * fielddata, SoInput * in);
  void get(SbString & fielddata, SoOutput * out);

  virtual void notify(SoNotList * l);

  virtual SbBool validateNewFieldValue(SoField * field, void * newval);

  virtual void addWriteReference(SoOutput * out, SbBool isfromfield = FALSE);
  virtual void writeInstance(SoOutput * out);

  SbBool getIsBuiltIn(void) const;
  virtual const SoFieldData * getFieldData(void) const;

  virtual void copyContents(const SoFieldContainer * from,
                            SbBool copyconnections);
  virtual SoFieldContainer * copyThroughConnection(void) const;

  static void initCopyDict(void);
  static void addCopy(const SoFieldContainer * orig,
                      const SoFieldContainer * copy);
  static SoFieldContainer * checkCopy(const SoFieldContainer * orig);
  static SoFieldContainer * findCopy(const SoFieldContainer * orig,
                                     const SbBool copyconnections);
  static void copyDone(void);

protected:
  SoFieldContainer(void);
  ~SoFieldContainer();

  virtual SbBool readInstance(SoInput * in, unsigned short flags);
  SbBool isBuiltIn;

private:
  static SoType classTypeId;
  SbBool donotify;
};

#ifdef __PIVY__
%clear SbString & fielddata;
%clear SoFieldList & l;
%clear SoFieldList & l_inout;
#endif

#endif // !COIN_SOFIELDCONTAINER_H
