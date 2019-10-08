
# encoding: utf8

# Copyright (c) 2006 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 2 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see http://www.gnu.org/licenses/.
#
# Author: David Malcolm

from __future__ import print_function

from six import PY2
import re
import unittest
import tempfile
import sys
import codecs

namespaces = [ ('desktop', ['evolution', 'openoffice.org', 'poppler', 'shared-mime-info']),
               ('tools', ['gcc']),
               ('CoreOS', ['rpm']),
               ('cluster', []),
               ('rhn', []) ]

def get_namespace_for_package(packageName):
    for (namespace, packages) in namespaces:
        if packageName in packages:
            return namespace

    # not found:
    return None
    
class TestInfo(object):
    """Class representing metadata about a test, suitable for outputting as a
    testinfo.desc file"""
    def __init__(self):
        self.test_name = None
        self.test_description = None
        self.test_archs = []
        self.owner = None
        self.testversion = None
        self.releases = []
        self.priority = None
        self.destructive = None
        self.license = None
        self.confidential = None
        self.avg_test_time = None
        self.test_path = None
        self.requires = []
        self.rhtsrequires = []
        self.runfor = []
        self.bugs = []
        self.types = []
        self.needs = []
        self.need_properties = []
        self.siteconfig = []
        self.kickstart = None
        self.options = []
        self.environment = {}
        self.provides = []

    def output_string_field(self, file, fileFieldName, dictFieldName):
        value = self.__dict__[dictFieldName]
        if value:
            file.write(u'%s: %s\n'%(fileFieldName, value))

    def output_string_list_field(self, file, fileFieldName, dictFieldName):
        value = self.__dict__[dictFieldName]
        if value:
            file.write(u'%s: %s\n'%(fileFieldName, u' '.join(value)))

    def output_string_dict_field(self, file, fileFieldName, dictFieldName):
        value = self.__dict__[dictFieldName]
        if value:
            for key, val in value.items():
                if val:
                    file.write(u'%s: %s=%s\n'%(fileFieldName, key, val))

    def output_bool_field(self, file, fileFieldName, dictFieldName):        
        value = self.__dict__[dictFieldName]
        if value is not None:
            if value:
                strValue = u"yes"
            else:
                strValue = u"no"
            file.write(u'%s: %s\n'%(fileFieldName, strValue))

    def output(self, file):
        """
        Write out a testinfo.desc to the file object
        """
        file = codecs.getwriter('utf8')(file)
        self.output_string_field(file, u'Name', u'test_name')
        self.output_string_field(file, u'Description', u'test_description')
        self.output_string_list_field(file, u'Architectures', u'test_archs')
        self.output_string_field(file, u'Owner', u'owner')
        self.output_string_field(file, u'TestVersion', u'testversion')
        self.output_string_list_field(file, u'Releases', u'releases')
        self.output_string_field(file, u'Priority', u'priority')
        self.output_bool_field(file, u'Destructive', u'destructive')
        self.output_string_field(file, u'License', u'license')
        self.output_bool_field(file, u'Confidential', u'confidential')
        self.output_string_field(file, u'TestTime', u'avg_test_time')
        self.output_string_field(file, u'Path', u'test_path')
        self.output_string_list_field(file, u'Requires', u'requires')
        self.output_string_list_field(file, u'RhtsRequires', u'rhtsrequires')
        self.output_string_list_field(file, u'RunFor', u'runfor')
        self.output_string_list_field(file, u'Bugs', u'bugs')
        self.output_string_list_field(file, u'Type', u'types')
        self.output_string_list_field(file, u'RhtsOptions', u'options')
        self.output_string_dict_field(file, u'Environment', u'environment')
        self.output_string_list_field(file, u'Provides', u'provides')
        for (name, op, value) in self.need_properties:
            file.write(u'NeedProperty: %s %s %s\n'%(name, op, value))
        file.write(self.generate_siteconfig_lines())
        
    def generate_siteconfig_lines(self):
        result = ""
        for (arg, description) in self.siteconfig:
            if self.test_name:
                if arg.startswith(self.test_name):
                    # Strip off common prefix:
                    arg = arg[len(self.test_name)+1:]
            result += u'SiteConfig(%s): %s\n'%(arg, description)
        return result
        
class Validator(object):
    """
    Abstract base class for validating fields
    """
    pass

class RegexValidator(Validator):
    def __init__(self, pattern, message):
        self.pattern = pattern
        self.msg = message

    def is_valid(self, value):
        return re.match(self.pattern, value)

    def message(self):
        return self.msg

class UnicodeRegexValidator(RegexValidator):
    """
    Validates against a regexp pattern but with the re.UNICODE flag applied
    so that character classes like \w have their "Unicode-aware" meaning.
    """
    def is_valid(self, value):
        return re.match(self.pattern, value, re.UNICODE)

# This is specified in RFC2822 Section 3.4, 
# we accept only the most common variations
class NameAddrValidator(UnicodeRegexValidator):

    ATOM_CHARS = r"\w!#$%&'\*\+-/=?^_`{|}~"
    PHRASE = r' *[%s][%s ]*' % (ATOM_CHARS, ATOM_CHARS)
    ADDR_SPEC = r'[%s.]+@[%s.]+' % (ATOM_CHARS, ATOM_CHARS)
    NAME_ADDR = r'%s<%s> *' % (PHRASE, ADDR_SPEC)

    def __init__(self):
        RegexValidator.__init__(self, self.NAME_ADDR,
                'should be a valid RFC2822 name_addr, '
                'such as John Doe <jdoe@somedomain.org>')

class ListValidator(Validator):
    def __init__(self, validValues):
        self.validValues = validValues

    def is_valid(self, value):
        return value in self.validValues

    def message(self):
        errorMsg = 'valid values are'
        for value in self.validValues:
            errorMsg += ' "%s"'%value
        return errorMsg

class DashListValidator(ListValidator):
    def is_valid(self, value):
        if value.startswith('-'):
            value = value[1:]
        return ListValidator.is_valid(self, value)

    def message(self):
        return ListValidator.message(self) + " optionally prefixed with '-'"

class BoolValidator(Validator):
    def __init__(self):
        pass

    def convert(self, value):
        if re.match("y|yes|1", value):
            return True

        if re.match("n|no|0", value):
            return False

        return None

    def is_valid(self, value):
        return self.convert(value) is not None

    def message(self):
        return "boolean value expected"


class Parser(object):
    """
    Parser for testinfo.desc files
    """
    def __init__(self):
        self.info = TestInfo()

        # All of these could be populated based on a DB query if we wanted to structure things that way:
        self.valid_root_ns = [
            'distribution', 
            'installation', 
            'kernel', 
            'desktop', 
            'tools', 
            'CoreOS', 
            'cluster', 
            'rhn', 
            'examples',
            'performance',
            'ISV',
            'virt'
            ]
        
        self.root_ns_with_mnt_tests_subtree = ['distribution', 'kernel']
        
        self.valid_architectures = [
            'ia64', 
            'x86_64', 
            'ppc', 
            'ppc64', 
            'ppc64le',
            's390', 
            's390x', 
            'i386',
            'aarch64',
            'arm',
            'armhfp',
            ]
        
        self.valid_priorities = [
            'Low', 
            'Medium', 
            'Normal', 
            'High', 
            'Manual'
            ]

        self.valid_options = [
            'Compatible',
            'CompatService',
            'StrongerAVC',
            ]
        
    def handle_error(self, message):
        raise NotImplementedError

    def handle_warning(self, message):
        raise NotImplementedError

    def error_if_not_in_array(self, fieldName, value, validValues):
        if not value in validValues:
            errorMsg = '"%s" is not a valid value for %s; valid values are'%(value, fieldName);
            for validValue in validValues:
                errorMsg += ' "%s"'%validValue
            self.handle_error(errorMsg)

    def __mandatory_field(self, fileFieldName, dictFieldName):
        if not self.info.__dict__[dictFieldName]:
            self.handle_error("%s field not defined"%fileFieldName)

    def __unique_field(self, fileFieldName, dictFieldName, value, validator=None):
        if self.info.__dict__[dictFieldName]:
            self.handle_error("%s field already defined"%fileFieldName)

        self.info.__dict__[dictFieldName] = value

        if validator:
            if not validator.is_valid(value):
                self.handle_error('"%s" is not a valid %s field (%s)'%(value, fileFieldName, validator.message()))

    def __bool_field(self, fileFieldName, dictFieldName, raw_value):
        validator = BoolValidator()
        if not validator.is_valid(raw_value):
            self.handle_error('"%s" is not a valid %s field (%s)'
                    % (raw_value, fileFieldName, validator.message()))
        value = validator.convert(raw_value)
        self.__unique_field(fileFieldName, dictFieldName, value)

    def _handle_dict(self, fileFieldName, dictFieldName, value, validator=None, key_validator=None):
        kv = value.split("=", 1)
        if len(kv) < 2:
            self.handle_error("Malformed %s field not matching KEY=VALUE pattern" % fileFieldName)
            return
        k, v = kv
        d = getattr(self.info, dictFieldName)
        if k in d:
            self.handle_error("%s: Duplicate entry for %r" % (fileFieldName, k))
            return
        if key_validator and not key_validator.is_valid(k):
            self.handle_error('"%s" is not a valid key for %s field (%s)'%(k, fileFieldName, key_validator.message()))
            return
        if validator and not validator.is_valid(v):
            self.handle_error('"%s" is not a valid %s field (%s)'%(v, fileFieldName, validator.message()))
            return
        d[k] = kv[1]

    def _handle_unique_list(self, fileFieldName, dictFieldName, value, validator=None, split_at=" "):
        l = getattr(self.info, dictFieldName)
        if l:
            self.handle_error("%s field already defined"%fileFieldName)
            return
        items = value.split(split_at)
        if validator:
            for item in items:
                if not validator.is_valid(item):
                    self.handle_error('"%s" is not a valid %s field (%s)'%(item, fileFieldName, validator.message()))
                    continue
                l.append(item)
        else:
            l.extend(items)

    def handle_name(self, key, value):
        self.__unique_field(key, 'test_name', value)

        if not re.match('^/', value):
            self.handle_error("Name field does not begin with a forward-slash")
            return
                
        name_frags= value.split('/')
        
        #print name_frags
        root_ns = name_frags[1]
        
        self.info.test_name_root_ns = root_ns
        self.info.test_name_under_root_ns = "/".join(name_frags[2:])
        self.info.expected_path_under_mnt_tests_from_name = self.info.test_name_under_root_ns
        # print "name_under_root_ns: %s"%self.info.test_name_under_root_ns            
        self.info.test_name_frags = name_frags

    def handle_desc(self, key, value):
        self.__unique_field(key, 'test_description', value)

    def handle_owner(self, key, value):
        # Required one-only email addresses "John Doe <someone@some.domain.org>"
        # In theory this could be e.g. memo-list@redhat.com; too expensive to check for that here
        self.__unique_field(key, 'owner', value, NameAddrValidator())

    def handle_testversion(self, key, value):
        self.__unique_field(key, 'testversion', value, RegexValidator(r'^([A-Za-z0-9\.]*)$', 'can only contain numbers, letters and the dot symbol'))
        # FIXME: we can probably support underscores as well

    def handle_license(self, key, value):
        self.__unique_field(key, 'license', value)

    def handle_deprecated(self, key, value):
        self.handle_warning("%s field is deprecated"%key)

    def handle_releases(self, key, value):
        self.__unique_field(key, 'releases', value)

        num_negative_releases = 0
        num_positive_releases = 0

        releases = []
        for release in value.split(" "):
            #print "Got release: release"

            releases.append(release)
            m = re.match('^-(.*)', release)
            if m:
                cleaned_release = m.group(1)
                # print "Got negative release: %s"%cleaned_release
                num_negative_releases+=1
            else:
                cleaned_release = release
                # print "Got positive release: %s"%release
                num_positive_releases+=1

            if num_negative_releases>0 and num_positive_releases>0:
                self.handle_warning("Releases field lists both negated and non-negated release names (should be all negated, or all non-negated)")
        self.info.releases = releases

    def handle_archs(self, key, value):
        self.__unique_field(key, 'test_archs', value)

        archs = []
        for arch in value.split(" "):
            self.error_if_not_in_array("Architecture", arch.lstrip('-'), self.valid_architectures)
            archs.append(arch)
        if any(arch.startswith('-') for arch in archs) and not all(arch.startswith('-') for arch in archs):
            self.handle_warning("Architectures field lists both negated and non-negated architectures (should be all negated, or all non-negated)")
        self.info.test_archs = archs

    def handle_options(self, key, value):
        self._handle_unique_list(key, 'options', value, DashListValidator(self.valid_options))

    def handle_environment(self, key, value):
        self._handle_dict(key, 'environment', value, key_validator=RegexValidator(r'^([A-Za-z_][A-Za-z0-9_]*)$', 'Can contain only letters, numbers and underscore.'))

    def handle_priority(self, key, value):
        self.__unique_field(key, 'priority', value, ListValidator(self.valid_priorities))

    def handle_destructive(self, key, value):
        self.__bool_field(key, 'destructive', value)

    def handle_confidential(self, key, value):
        self.__bool_field(key, 'confidential', value)

    def handle_testtime(self, key, value):
        if self.info.avg_test_time:
            self.handle_error("%s field already defined"%key)
            return

        # TestTime is an integer with an optional minute (m) or hour (h) suffix
        m = re.match('^(\d+)(.*)$', value)
        if m:
            self.info.avg_test_time = int(m.group(1))
            suffix = m.group(2)
            if suffix == '':
                pass # no units means seconds
            elif suffix == 'm':
                self.info.avg_test_time *= 60
            elif suffix == 'h':
                self.info.avg_test_time *= 3600
            else:
                self.handle_warning("TestTime unit is not valid, should be m (minutes) or h (hours)")
                return

            if self.info.avg_test_time<60:
                self.handle_warning("TestTime should not be less than a minute")

        else:
            self.handle_error("Malformed %s field"%key)

    def handle_type(self, key, value):
        for type in value.split(" "):
            self.info.types.append(type)
    
    def handle_kickstart(self, key, value):
        self.info.kickstart = value
    
    def handle_bug(self, key, value):
        for bug in value.split(" "):
            # print "Got bug: %s"%bug

            m = re.match('^([1-9][0-9]*)$', bug)
            if m:
                self.info.bugs.append(int(m.group(1)))
            else:
                self.handle_error('"%s" is not a valid Bug value (should be numeric)'%bug)
                
    def handle_path(self, key, value):
        if self.info.test_path:
            self.handle_error("Path field already defined")

        if re.match(r'^\/mnt\/tests\/', value):
            absolute_path = value
        else:
            if re.match(r'^\/', value):
                self.handle_error("Path field is absolute but is not below /mnt/tests")

            # Relative path:

            absolute_path = "/mnt/tests/"+value

        self.info.test_path = absolute_path

#			$absolute_path =~ /^\/mnt\/tests\/(.*)$/;
#			my $test_path_under_mnt_tests = $1;
#
#			# Deal with trailing slashes:
#			chop $test_path_under_mnt_tests if $test_path_under_mnt_tests =~ m/\/$/;
#
#			$test{test_path_under_mnt_tests} = $test_path_under_mnt_tests;
#
#			# FIXME: ensure that the path value is sane...
#			# with the /mnt/tests stripped off it ought to be equal to 
#

    def handle_runfor(self, key, value):
        for pkgname in value.split(" "):
            self.info.runfor.append(pkgname)

    def handle_requires(self, key, value):
        for pkgname in value.split(" "):
            self.info.requires.append(pkgname)

    def handle_rhtsrequires(self, key, value):
        for pkgname in value.split(" "):
            self.info.rhtsrequires.append(pkgname)

    def handle_provides(self, key, value):
        for pkgname in value.split(" "):
            self.info.provides.append(pkgname)

    def handle_needproperty(self, key, value):
        m = re.match(r'^([A-Za-z0-9]*)\s+(=|>|>=|<|<=)\s+([A-Z:a-z0-9]*)$', value)
        if m:
            self.info.needs.append(value)
            self.info.need_properties.append((m.group(1), m.group(2), m.group(3)))
        else:
            self.handle_error('"%s" is not a valid %s field; %s'%(value, key, "must be of the form PROPERTYNAME {=|>|>=|<|<=} PROPERTYVALUE"))

    def handle_deprecated_for_needproperty(self, key, value):
        self.handle_error("%s field is deprecated.  Use NeedProperty instead"%key)

    def __handle_siteconfig(self, arg, value):
        if re.match('^/.*', arg):
            # Absolute path:
            absPath = arg
        else:
            # Relative path:
            if self.info.test_name:
                absPath = self.info.test_name + '/' + arg
            else:
                self.handle_error("A relative SiteConfig(): declaration appeared before a Name: field")
                return
        self.info.siteconfig.append( (absPath, value) )
    
    def __handle_declaration(self, decl, arg, value):
        # print 'decl:  "%s"'%decl
        # print 'arg:   "%s"'%arg
        # print 'value: "%s"'%value

        if decl=="SiteConfig":
            self.__handle_siteconfig(arg, value)
        else:
            self.handle_error('"%s" is not a valid declaration"')
        
    def parse(self, lines):
        # Map from field names to value-parsing methods:
        fields = {'Name' : self.handle_name,
                  'Description' : self.handle_desc,
                  'Notify' : self.handle_deprecated,
                  'Owner' : self.handle_owner,
                  'TestVersion' : self.handle_testversion,
                  'License' : self.handle_license,
                  'Releases': self.handle_releases,
                  'Architectures': self.handle_archs,
                  'RhtsOptions': self.handle_options,
                  'Environment': self.handle_environment,
                  'Priority': self.handle_priority,
                  'Destructive': self.handle_destructive,
                  'Confidential': self.handle_confidential,
                  'TestTime': self.handle_testtime,
                  'Type': self.handle_type,
                  'Bug': self.handle_bug,
                  'Bugs': self.handle_bug,
                  'Path': self.handle_path,
                  'RunFor': self.handle_runfor,
                  'Requires': self.handle_requires,
                  'RhtsRequires': self.handle_rhtsrequires,
                  'NeedProperty': self.handle_needproperty,
                  'Need': self.handle_deprecated_for_needproperty,
                  'Want': self.handle_deprecated_for_needproperty,
                  'WantProperty': self.handle_deprecated_for_needproperty,
                  'Kickstart': self.handle_kickstart,
                  'Provides': self.handle_provides,
                  }

        self.lineNum = 0;
        for line in lines:
            self.lineNum+=1

            # print $line_num," ",$line;

            # Skip comment lines:
            if re.match('^#', line):
                continue

            line = line.strip()
 
            # Skip pure whitespace:
            if line=='':
                continue

            # Handle declarations e.g. "SiteConfig(server):  hostname of server"
            m = re.match('([^:]*)\((.*)\):(.*)', line)
            if m:
                (decl, arg, value) = (m.group(1), m.group(2), m.group(3))

                # Deal with it, stripping whitespace:
                self.__handle_declaration(decl, arg.strip(), value.strip())
                continue

            # Handle key/value pairs e.g.: "Bug: 123456"
            m = re.match('([^:]*):(.*)', line)
            if not m:
                self.handle_error("Malformed \"Key: value\" line")
                continue
            
            (key, value) = (m.group(1), m.group(2))
            
            # Strip leading and trailing whitespace:
            value = value.strip()

            # Note that I'm not quoting the values; this isn't talking direct to a DB
            if key in fields:
                handler = fields[key]
                handler(key, value)

        # Postprocessing:
	# Ensure mandatory fields have values:
        self.__mandatory_field('Name', 'test_name')
        self.__mandatory_field('Description', 'test_description')
        self.__mandatory_field('Path', 'test_path')
        self.__mandatory_field('TestTime', 'avg_test_time')
        self.__mandatory_field('TestVersion', 'testversion')
        self.__mandatory_field('License', 'license')
        self.__mandatory_field('Owner', 'owner')

#
#	my $expected_path_under_mnt_tests = $test{test_name_under_root_ns};
#
#	# Some root namespaces seem to expect tests to live under /mnt/tests/ROOT_NS_NAME:
#    foreach my $root_ns (@root_ns_with_mnt_tests_subtree) {
#		if ($test{test_name_root_ns} eq $root_ns) {
#			$expected_path_under_mnt_tests = "$root_ns/$expected_path_under_mnt_tests";
#		}
#	}
#
#	#print "Name: $test{test_name}\n";
#	#print "Path: $test{test_path}\n\n";
#	#print "                  root_ns: $test{test_name_root_ns}\n";
#	#print "       name_under_root_ns: $test{test_name_under_root_ns}\n";
#	#print "test_path_under_mnt_tests: $test{test_path_under_mnt_tests}\n";
#	#print "            expected path: $test{expected_path_under_mnt_tests_from_name}\n";
#
#	if (!($test{test_path_under_mnt_tests} eq $expected_path_under_mnt_tests)) {
#		# Disable for now: a few true positives, but many false positives:
#		#&handle_error($filename, "Path below /mnt/tests (\"$test{test_path_under_mnt_tests}\") does not match expected value (\"$expected_path_under_mnt_tests\") based on Name ", $line_num);
#	}
#
#
#	# FIXME: warn about RunFor: in conjunction with Priority: Manual
#
#	# FIXME: warn about Requires: not containing RunFor: ?
#	# FIXME: warn about RunFor: not containing Requires: ?
#	# FIXME: warn about a test against a specific package (via the Name and/or Path ?) not containing RunFor: and Requires: lines ? (if not manual???)
#	# FIXME: warn about mismatch between Name and Path ?
#	# FIXME: warn about NeedProperty names,values, operators
#	# FIXME: blank RunFor: lines
#	
#	# Server side FIXMEs:
#	# query the tree for Requires/RunFor package names to ensure these are sane
#
#	# Stuff we could lint for in the runtest.sh:
#	# - that it exists
#	# - that it's syntactically valid
#	# - that you use report_result specifically with $result when using startup_test (special var)
#
#	# Stuff we could lint for in the Makefile:
#	# - that it's syntactically valid?
#	# - the usual tab issues in Makefiles
#	# - must contain an install target
#	# - not having install as the top-most target ????
#
##lintable stuff from actual cleanups:
##-       export result="FAIL:"
##+       export result="FAIL"
#
#
#
#    # Do some post processing, like turning lists into strings
#    # Only do the processing if we found the field while parsing
#    # Remove the temporary key if it existed
#    if (exists $test{RunFor}) {
#        #$test{relevant_packages} = $db->quote(join ' ', @{$test{RunFor}});
#        #delete $test{RunFor};
#    }
#    if (exists $test{Requires}) {
#        #$test{packages_needed} = $db->quote(join ' ', @{$test{Requires}});
#        #delete $test{Requires};
#    }
#    if (exists $test{Need}) {
#        #foreach my $prop (@{$test{Need}}) {
#        #    $test{need_property} .= "NeedProperty $prop\n";
#        #}
#        #delete $test{Need};
#        #$test{need_property} = $db->quote($test{need_property});
#    }
#    if (exists $test{Want}) {
#        #foreach my $prop (@{$test{Want}}) {
#        #    $test{want_property} .= "WantProperty $prop\n";
#        #}
#        #delete $test{Want};
#        #$test{want_property} = $db->quote($test{want_property});
#    }
#    # All values should be properly quoted by this point.
#
#    # build up a list to use with SQL "WHERE x in list"
#    #my $testtype = join "', '", @testtypes;
#    #$testtype = "('$testtype')";
#}

class PrintingParser(Parser):
    """
    A parser which handles errors/warnings by printing messages to a file object
    """
    def __init__(self, outputFileObj, inputFilename):
        Parser.__init__(self)
        self.outputFileObj = outputFileObj
        self.inputFilename = inputFilename
        self.numErrors = 0
        self.numWarnings = 0

    def handle_message(self, message, severity):
        # Try to mimic the format of a GCC output line, e.g.:
        # tmp.c:1: error: there is a problem with your code
        print("%s:%i: %s: %s"%(self.inputFilename, self.lineNum, severity, message), file=self.outputFileObj)

    def handle_error(self, message):
        self.handle_message(message, "error")
        self.numErrors+=1

    def handle_warning(self, message):
        self.handle_message(message, "warning")
        self.numWarnings+=1

class StdoutParser(PrintingParser):
    """
    A parser which handles errors/warnings by printing messages to stdout
    """
    def __init__(self, inputFilename):
        PrintingParser.__init__(self, sys.stdout, inputFilename)
    
class StderrParser(PrintingParser):
    """
    A parser which handles errors/warnings by printing messages to stderr
    """
    def __init__(self, inputFilename):
        PrintingParser.__init__(self, sys.stderr, inputFilename)


class ParserError(Exception):
    pass

class ParserWarning(Exception):
    pass

class StrictParser(Parser):
    def __init__(self, raise_errors):
        Parser.__init__(self)
        self.raise_errors = raise_errors
    
    def handle_error(self, message):
        if self.raise_errors:
            raise ParserError(message)

    def handle_warning(self, message):
        if self.raise_errors:
            raise ParserWarning(message)

def parse_string(string, raise_errors = True):
    if isinstance(string, str) and PY2:
        # Callers should always pass unicode for consistency, this is just to 
        # be forgiving so we don't break anyone unexpectedly.
        string = string.decode('utf8')
    p = StrictParser(raise_errors)
    p.parse(string.split("\n"))
    return p.info

def parse_file(filename, raise_errors = True):
    p = StrictParser(raise_errors)
    with codecs.open(filename, 'rb', 'utf8') as fd:
        p.parse(fd.readlines())
    return p.info

#class ParserTests(unittest.TestCase):
#    def test_key_value(self):
#        raise NotImplementedError
#
#    def test_decl_arg_value(self):
#        raise NotImplementedError

class NamespaceTests(unittest.TestCase):
    def test_package_not_found(self):
        "Ensure that we get None for the namespace of an unrecognized package"
        self.assertEqual(None, get_namespace_for_package('foobar'))

    def test_simple_packages(self):
        "Ensure that we get expected namespaces back for some simple packages"
        self.assertEqual('desktop', get_namespace_for_package('evolution'))
        self.assertEqual('tools', get_namespace_for_package('gcc'))

class NameFieldTests(unittest.TestCase):
    def test_name(self):
        "Ensure Name field is parsed correctly"
        ti = parse_string(u"Name: /CoreOS/cups/foo/bar", raise_errors=False)
        self.assertEqual(ti.test_name, u"/CoreOS/cups/foo/bar")

class PathFieldTests(unittest.TestCase):
    def test_path_absolute(self):
        "Ensure absolute Path field is parsed correctly"
        ti = parse_string(u"Path: /mnt/tests/CoreOS/cups/foo/bar", raise_errors=False)
        self.assertEqual(ti.test_path, u"/mnt/tests/CoreOS/cups/foo/bar")

    def test_path_relative(self):
        "Ensure relative Path field is parsed correctly"
        ti = parse_string(u"Path: CoreOS/cups/foo/bar", raise_errors=False)
        self.assertEqual(ti.test_path, u"/mnt/tests/CoreOS/cups/foo/bar")

class DescriptionFieldTests(unittest.TestCase):
    def test_description(self):
        "Ensure Description field is parsed correctly"
        ti = parse_string(u"Description: Ensure that the thingummy frobnicates the doohickey", raise_errors=False)
        self.assertEqual(ti.test_description, u"Ensure that the thingummy frobnicates the doohickey")

    def test_description_with_colon(self):
        "Ensure Description field containing a colon is parsed correctly"
        ti = parse_string(u"Description: This test is from http://foo/bar", raise_errors=False)
        self.assertEqual(ti.test_description, u"This test is from http://foo/bar")

class ReleasesFieldTests(unittest.TestCase):
    def test_releases(self):
        "Ensure Releases field is parsed correctly"
        ti = parse_string(u"Releases: FC5 FC6", raise_errors=False)
        self.assertEqual(ti.releases, [u'FC5', u'FC6'])

class ArchitecturesFieldTests(unittest.TestCase):
    def test_architectures(self):
        "Ensure Architectures field is parsed correctly"
        ti = parse_string(u"Architectures: i386 x86_64", raise_errors=False)
        self.assertEqual(ti.test_archs, [u"i386", u"x86_64"])

    def test_architectures_after_releases(self):
        "Ensure that an Architectures field following a Releases field is parsed correctly"
        ti = parse_string(u"""
        Releases: FC5 FC6
        Architectures: i386 x86_64""", raise_errors=False)
        self.assertEqual(ti.releases, [u'FC5', u'FC6'])
        self.assertEqual(ti.test_archs, [u"i386", u"x86_64"])

class RhtsOptionsFieldTests(unittest.TestCase):
    def test_rhtsoptions(self):
        "Ensure RhtsOptions field is parsed correctly"
        ti = parse_string(u"RhtsOptions: Compatible", raise_errors=False)
        self.assertEqual(ti.options, [u"Compatible"])

    def test_multi_options(self):
        "Ensure RhtsOptions field is parsed correctly"
        ti = parse_string(u"RhtsOptions: Compatible -CompatService -StrongerAVC", raise_errors=False)
        self.assertEqual(ti.options, [u"Compatible", u"-CompatService", u"-StrongerAVC"])

    def test_rhtsoptions_minus(self):
        "Ensure RhtsOptions field parses options preceded with dash correctly"
        ti = parse_string(u"RhtsOptions: -Compatible", raise_errors=False)
        self.assertEqual(ti.options, [u"-Compatible"])

    def test_rhtsoption_bad_value(self):
        "Ensure RhtsOptions field captures bad input"
        self.assertRaises(ParserError, parse_string, u"RhtsOptions: Compat", raise_errors=True)

    def test_rhtsoption_duplicate(self):
        "Ensure RhtsOptions field captures duplicate entries"
        self.assertRaises(ParserError, parse_string, u"RhtsOptions: Compatible\nRhtsOptions: -Compatible", raise_errors=True)

class EnvironmentFieldTests(unittest.TestCase):
    def test_environment(self):
        "Ensure Environment field is parsed correctly"
        ti = parse_string(u"Environment: VAR1=VAL1\nEnvironment: VAR2=Value with spaces - 2", raise_errors=False)
        self.assertEqual(ti.environment["VAR1"], u"VAL1")
        self.assertEqual(ti.environment["VAR2"], u"Value with spaces - 2")

    def test_environment_duplicate_key(self):
        "Ensure Environment field captures duplicate keys"
        self.assertRaises(ParserError, parse_string, u"Environment: VAR1=VAL1\nEnvironment: VAR1=Value with spaces - 2", raise_errors=True)

    def test_environment_bad_key(self):
        "Ensure Environment field captures bad keys"
        self.assertRaises(ParserError, parse_string, u"Environment: VAR =VAL1", raise_errors=True)

class NotifyFieldTests(unittest.TestCase):
    def test_notify(self):
        "Ensure Notify field is deprecated"
        self.assertRaises(ParserWarning, parse_string, u"Notify: everyone in a 5-mile radius", raise_errors=True)

class OwnerFieldTests(unittest.TestCase):
    def test_owner_example(self):
        "Ensure that the example Owner field is parsed correctly"
        ti = parse_string(u"Owner: John Doe <jdoe@redhat.com>", raise_errors=False)
        self.assertEqual(ti.owner, u"John Doe <jdoe@redhat.com>")

    def test_owner_example2(self):
        "Ensure that other Owner fields are parsed correctly"
        ti = parse_string(u"Owner: Jane Doe <jdoe@fedoraproject.org>", raise_errors=False)
        self.assertEqual(ti.owner, u"Jane Doe <jdoe@fedoraproject.org>")

    # https://bugzilla.redhat.com/show_bug.cgi?id=723159
    def test_owner_with_hyphen(self):
        parser = StrictParser(raise_errors=True)
        parser.handle_owner('Owner', u'Endre Balint-Nagy <endre@redhat.com>')
        self.assertEqual(parser.info.owner, u'Endre Balint-Nagy <endre@redhat.com>')

    # https://bugzilla.redhat.com/show_bug.cgi?id=1491658
    def test_non_ascii_owner(self):
        parser = StrictParser(raise_errors=True)
        parser.handle_owner('Owner', u'Gęśla Jaźń <gj@example.com>')
        self.assertEqual(parser.info.owner, u'Gęśla Jaźń <gj@example.com>')

class PriorityFieldTests(unittest.TestCase):
    def test_priority(self):
        "Ensure Priority field is parsed correctly"
        ti = parse_string(u"Priority: Manual", raise_errors=False)
        self.assertEqual(ti.priority, u"Manual")

class BugFieldTests(unittest.TestCase):
    def test_single_bug(self):
        "Ensure a single Bug field works"
        ti = parse_string(u"Bug: 123456", raise_errors=False)
        self.assertEqual(ti.bugs, [123456])

    def test_single_bugs(self):
        "Ensure a single Bugs field works"
        ti = parse_string(u"Bugs: 123456", raise_errors=False)
        self.assertEqual(ti.bugs, [123456])

    def test_multiple_bugs(self):
        "Ensure that multiple values for a Bugs field work"
        ti = parse_string(u"Bugs: 123456 456123", raise_errors=False)
        self.assertEqual(ti.bugs, [123456, 456123])

    def test_multiple_bug_lines(self):
        "Ensure that multiple Bug and Bugs lines work"
        ti = parse_string(u"""Bugs: 123456 456123
        Bug: 987654 456789""", raise_errors=False)
        self.assertEqual(ti.bugs, [123456, 456123, 987654, 456789])

    def test_blank_bug(self):
        "Ensure a blank Bug field is handled"
        ti = parse_string(u"Bug: ", raise_errors=False)
        self.assertEqual(ti.bugs, [])

class TestVersionFieldTests(unittest.TestCase):
    def test_testversion(self):
        "Ensure TestVersion field is parsed correctly"
        ti = parse_string(u"TestVersion: 1.1", raise_errors=False)
        self.assertEqual(ti.testversion, u"1.1")

class LicenseFieldTests(unittest.TestCase):
    def test_license(self):
        "Ensure License field is parsed correctly"
        ti = parse_string(u"License: GPL", raise_errors=False)
        self.assertEqual(ti.license, u"GPL")

class TestTimeFieldTests(unittest.TestCase):
    def test_testtime_seconds(self):
        "Ensure TestTime field can handle seconds"
        ti = parse_string(u"TestTime: 5", raise_errors=False)
        self.assertEqual(ti.avg_test_time, 5)

    def test_testtime_minutes(self):
        "Ensure TestTime field can handle minutes"
        ti = parse_string(u"TestTime: 10m", raise_errors=False)
        self.assertEqual(ti.avg_test_time, 600)

    def test_testtime_hours(self):
        "Ensure TestTime field can handle hours"
        ti = parse_string(u"TestTime: 2h", raise_errors=False)
        self.assertEqual(ti.avg_test_time, (2*60*60))

class RequiresFieldTests(unittest.TestCase):
    def test_single_line_requires(self):
        "Ensure Requires field is parsed correctly"
        ti = parse_string(u"Requires: evolution dogtail", raise_errors=False)
        self.assertEqual(ti.requires, [u'evolution', u'dogtail'])

    def test_multiline_requires(self):
        "Ensure we can handle multiple Requires lines"
        ti = parse_string(u"""Requires: evolution dogtail
        Requires: foo bar""", raise_errors=False)
        self.assertEqual(ti.requires, [u'evolution', u'dogtail', u'foo', u'bar'])

    def test_requires_with_case_differences(self):
        "Ensure Requires field is parsed correctly"
        ti = parse_string(u"Requires: opencryptoki openCryptoki", raise_errors=False)
        self.assertEqual(ti.requires, [u'opencryptoki', u'openCryptoki'])

class RunForFieldTests(unittest.TestCase):
    def test_single_line_runfor(self):
        "Ensure RunFor field is parsed correctly"
        ti = parse_string(u"RunFor: evolution dogtail", raise_errors=False)
        self.assertEqual(ti.runfor, [u'evolution', u'dogtail'])

    def test_multiline_runfor(self):
        "Ensure we can handle multiple RunFor lines"
        ti = parse_string(u"""RunFor: evolution dogtail
        RunFor: foo bar""", raise_errors=False)
        self.assertEqual(ti.runfor, [u'evolution', u'dogtail', u'foo', u'bar'])

class TypeFieldTests(unittest.TestCase):
    def test_single_line_type(self):
        "Ensure Type field is parsed correctly"
        ti = parse_string(u"Type: Crasher Regression", raise_errors=False)
        self.assertEqual(ti.types, [u'Crasher', u'Regression'])

    def test_multiline_type(self):
        "Ensure we can handle multiple Type lines"
        ti = parse_string(u"""Type: Crasher Regression
        Type: Performance Stress""", raise_errors=False)
        self.assertEqual(ti.types, [u'Crasher', u'Regression', u'Performance', u'Stress'])

class NeedPropertyFieldTests(unittest.TestCase):
    def test_single_line_needproperty(self):
        "Ensure NeedProperty field is parsed correctly"
        ti = parse_string(u"NeedProperty: PROCESSORS > 1", raise_errors=False)
        self.assertEqual(ti.need_properties, [(u"PROCESSORS", u">", u"1")])
                          
    def test_multiline_needproperty(self):
        "Ensure we can handle multiple NeedProperty lines"
        ti = parse_string(u"""
        NeedProperty: CAKE = CHOCOLATE
        NeedProperty: SLICES > 3
        """, raise_errors=False)
        self.assertEqual(ti.need_properties, [(u"CAKE", u"=", u"CHOCOLATE"), (u"SLICES", u">", u"3")])

class DestructiveFieldTests(unittest.TestCase):
    def test_destructive(self):
        ti = parse_string(u"Destructive: yes", raise_errors=False)
        self.assertEqual(ti.destructive, True)

class SiteConfigDeclarationTests(unittest.TestCase):
    """Unit tests for the SiteConfig declaration"""
    
    def test_relative_siteconfig_without_name(self):
        "Ensure that a relative SiteConfig declaration without a Name is handled with a sane error"
        self.assertRaises(ParserError, parse_string, u"SiteConfig(server): Hostname of server", raise_errors=True)

    def test_flat_relative_siteconfig(self):
        "Ensure that relative SiteConfig declarations without nesting work"
        ti = parse_string(u"""
        Name: /desktop/evolution/mail/imap/authentication/ssl
        SiteConfig(server): Hostname of server
        SiteConfig(username): Username to use
        SiteConfig(password): Password to use
        """, raise_errors=False)
        self.assertEqual(ti.siteconfig, [(u'/desktop/evolution/mail/imap/authentication/ssl/server', u"Hostname of server"),
                                          (u'/desktop/evolution/mail/imap/authentication/ssl/username', u"Username to use"),
                                          (u'/desktop/evolution/mail/imap/authentication/ssl/password', u"Password to use")
                                          ])

    def test_nested_relative_siteconfig(self):
        "Ensure that a relative SiteConfig declaration containing a path works"
        ti = parse_string(u"""
        Name: /desktop/evolution/mail/imap/authentication
        SiteConfig(ssl/server): Hostname of server to try SSL auth against
        SiteConfig(ssl/username): Username to use for SSL auth
        SiteConfig(ssl/password): Password to use for SSL auth
        SiteConfig(tls/server): Hostname of server to try TLS auth against
        SiteConfig(tls/username): Username to use for TLS auth
        SiteConfig(tls/password): Password to use for TLS auth
        """, raise_errors=False)
        self.assertEqual(ti.siteconfig, [(u'/desktop/evolution/mail/imap/authentication/ssl/server', u"Hostname of server to try SSL auth against"),
                                          (u'/desktop/evolution/mail/imap/authentication/ssl/username', u"Username to use for SSL auth"),
                                          (u'/desktop/evolution/mail/imap/authentication/ssl/password', u"Password to use for SSL auth"),
                                          (u'/desktop/evolution/mail/imap/authentication/tls/server', u"Hostname of server to try TLS auth against"),
                                          (u'/desktop/evolution/mail/imap/authentication/tls/username', u"Username to use for TLS auth"),
                                          (u'/desktop/evolution/mail/imap/authentication/tls/password', u"Password to use for TLS auth")
                                          ])

    def test_absolute_siteconfig(self):
        "Ensure that an absolute SiteConfig declaration works"
        ti = parse_string(u"""SiteConfig(/stable-servers/ldap/hostname): Location of stable LDAP server to use""", raise_errors=False)
        self.assertEqual(ti.siteconfig, [(u'/stable-servers/ldap/hostname', u'Location of stable LDAP server to use')])

    #def test_siteconfig_comment(self):
    #    "Ensure that comments are stripped as expected from descriptions"
    #    ti = parse_string("SiteConfig(/foo/bar): Some value # hello world", raise_errors=False)
    #    self.assertEqual(ti.siteconfig, [('/foo/bar', "Some value")])

    def test_siteconfig_whitespace(self):
        "Ensure that whitespace is stripped as expected from descriptions"
        ti = parse_string(u"SiteConfig(/foo/bar):        Some value    ", raise_errors=False)
        self.assertEqual(ti.siteconfig, [(u'/foo/bar', u"Some value")])

    def test_output_relative_siteconfig(self):
        "Ensure that the output methods collapse redundant paths in relative SiteConfig declarations"
        ti = TestInfo()
        ti.test_name = u'/foo/bar'
        ti.siteconfig = [(u'/foo/bar/baz/fubar', u'Dummy value')]
        self.assertEqual(ti.generate_siteconfig_lines(), u"SiteConfig(baz/fubar): Dummy value\n")
        

class IntegrationTests(unittest.TestCase):
    def test_example_file(self):
        "Ensure a full example file is parsed correctly"
        ti = parse_string(u"""\
# Test comment
Owner:        Jane Doe <jdoe@redhat.com>
Name:         /examples/coreutils/example-simple-test
Path:         /mnt/tests/examples/coreutils/example-simple-test
Description:  This test ensures that cafés are generated and validated correctly
TestTime:     1m
TestVersion:  1.1
License:      GPL
RunFor:       coreutils
Requires:     coreutils python
        """, raise_errors=True)
        self.assertEqual(ti.owner, u"Jane Doe <jdoe@redhat.com>")
        self.assertEqual(ti.test_name, u"/examples/coreutils/example-simple-test")
        self.assertEqual(ti.test_path, u"/mnt/tests/examples/coreutils/example-simple-test")
        self.assertEqual(ti.test_description, u"This test ensures that cafés are generated and validated correctly")
        self.assertEqual(ti.avg_test_time, 60)
        self.assertEqual(ti.testversion, u"1.1")
        self.assertEqual(ti.license, u"GPL")
        self.assertEqual(ti.runfor, [u"coreutils"])
        self.assertEqual(ti.requires, [u"coreutils", u"python"])

    def test_output_testinfo(self):
        "Output an example file, then ensure it is parsed succesfully"
        ti1 = parse_string(u"""\
# Test comment
Owner:        Jane Doe <jdoe@redhat.com>
Name:         /examples/coreutils/example-simple-test
Path:         /mnt/tests/examples/coreutils/example-simple-test
Description:  This test ensures that cafés are generated and validated correctly
TestTime:     1m
TestVersion:  1.1
License:      GPL
Destructive:  yes
RunFor:       coreutils
Requires:     coreutils python
NeedProperty: CAKE = CHOCOLATE
NeedProperty: SLICES > 3
SiteConfig(server): Hostname of server
SiteConfig(username): Username to use
SiteConfig(password): Password to use
SiteConfig(ssl/server): Hostname of server to try SSL auth against
SiteConfig(ssl/username): Username to use for SSL auth
SiteConfig(ssl/password): Password to use for SSL auth
SiteConfig(tls/server): Hostname of server to try TLS auth against
SiteConfig(tls/username): Username to use for TLS auth
SiteConfig(tls/password): Password to use for TLS auth
SiteConfig(/stable-servers/ldap/hostname): Location of stable LDAP server to use
        """, raise_errors=True)
        file = tempfile.NamedTemporaryFile(mode='wb')
        ti1.output(file)
        file.flush()

        ti2 = parse_file(file.name)
        self.assertEqual(ti2.owner, u"Jane Doe <jdoe@redhat.com>")
        self.assertEqual(ti2.test_name, u"/examples/coreutils/example-simple-test")
        self.assertEqual(ti2.test_path, u"/mnt/tests/examples/coreutils/example-simple-test")
        self.assertEqual(ti2.test_description, u"This test ensures that cafés are generated and validated correctly")
        self.assertEqual(ti2.avg_test_time, 60)
        self.assertEqual(ti2.testversion, u"1.1")
        self.assertEqual(ti2.license, u"GPL")
        self.assertEqual(ti2.destructive, True)
        self.assertEqual(ti2.runfor, [u"coreutils"])
        self.assertEqual(ti2.requires, [u"coreutils", u"python"])
        self.assertEqual(ti2.need_properties, [(u'CAKE', u'=', u'CHOCOLATE'), (u'SLICES', u'>', u'3')])
        self.assertEqual(ti2.siteconfig, [(u'/examples/coreutils/example-simple-test/server', u'Hostname of server'),
                                           (u'/examples/coreutils/example-simple-test/username', u'Username to use'),
                                           (u'/examples/coreutils/example-simple-test/password', u'Password to use'),
                                           (u'/examples/coreutils/example-simple-test/ssl/server', u'Hostname of server to try SSL auth against'),
                                           (u'/examples/coreutils/example-simple-test/ssl/username', u'Username to use for SSL auth'),
                                           (u'/examples/coreutils/example-simple-test/ssl/password', u'Password to use for SSL auth'),
                                           (u'/examples/coreutils/example-simple-test/tls/server', u'Hostname of server to try TLS auth against'),
                                           (u'/examples/coreutils/example-simple-test/tls/username', u'Username to use for TLS auth'),
                                           (u'/examples/coreutils/example-simple-test/tls/password', u'Password to use for TLS auth'),
                                           (u'/stable-servers/ldap/hostname', u'Location of stable LDAP server to use')])

#etc


if __name__=='__main__':
    unittest.main()
    
    
