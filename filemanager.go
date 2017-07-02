package filemanager

import (
	"errors"
	"net/http"
	"regexp"
	"strings"

	rice "github.com/GeertJohan/go.rice"
	"golang.org/x/net/webdav"
)

var (
	// ErrDuplicated occurs when you try to create a user that already exists.
	ErrDuplicated = errors.New("Duplicated user")
)

// FileManager is a file manager instance. It should be creating using the
// 'New' function and not directly.
type FileManager struct {
	*User

	// prefixURL is a part of the URL that is already trimmed from the request URL before it
	// arrives to our handlers. It may be useful when using File Manager as a middleware
	// such as in caddy-filemanager plugin. It is only useful in certain situations.
	prefixURL string

	// baseURL is the path where the GUI will be accessible. It musn't end with
	// a trailing slash and mustn't contain prefixURL, if set.
	baseURL string

	// Users is a map with the different configurations for each user.
	Users map[string]*User

	// BeforeSave is a function that is called before saving a file.
	BeforeSave Command

	// AfterSave is a function that is called before saving a file.
	AfterSave Command

	assets *rice.Box
}

// Command is a command function.
type Command func(r *http.Request, m *FileManager, u *User) error

// User contains the configuration for each user. It should be created
// using NewUser on a File Manager instance.
type User struct {
	// Scope is the physical path the user has access to.
	Scope string

	// fileSystem is the virtual file system the user has access.
	fileSystem webdav.FileSystem

	// Rules is an array of access and deny rules.
	Rules []*Rule `json:"-"`

	// TODO: this MUST be done in another way
	StyleSheet string `json:"-"`

	// These indicate if the user can perform certain actions.
	AllowNew      bool `json:"allowNew"`      // Create files and folders
	AllowEdit     bool `json:"allowEdit"`     // Edit/rename files
	AllowCommands bool `json:"allowCommands"` // Execute commands

	// Commands is the list of commands the user can execute.
	Commands []string `json:"commands"`
}

// Rule is a dissalow/allow rule.
type Rule struct {
	// Regex indicates if this rule uses Regular Expressions or not.
	Regex bool

	// Allow indicates if this is an allow rule. Set 'false' to be a disallow rule.
	Allow bool

	// Path is the corresponding URL path for this rule.
	Path string

	// Regexp is the regular expression. Only use this when 'Regex' was set to true.
	Regexp *regexp.Regexp
}

// New creates a new File Manager instance with the needed
// configuration to work.
func New(scope string) *FileManager {
	m := &FileManager{
		User: &User{
			AllowCommands: true,
			AllowEdit:     true,
			AllowNew:      true,
			Commands:      []string{},
			Rules:         []*Rule{},
		},
		Users:      map[string]*User{},
		BeforeSave: func(r *http.Request, m *FileManager, u *User) error { return nil },
		AfterSave:  func(r *http.Request, m *FileManager, u *User) error { return nil },
		assets:     rice.MustFindBox("./_assets/dist"),
	}

	m.SetScope(scope, "")
	m.SetBaseURL("/")

	return m
}

// RootURL returns the actual URL where
// File Manager interface can be accessed.
func (m FileManager) RootURL() string {
	return m.prefixURL + m.baseURL
}

// WebDavURL returns the actual URL
// where WebDAV can be accessed.
func (m FileManager) WebDavURL() string {
	return m.prefixURL + m.baseURL + "/api/webdav"
}

// SetPrefixURL updates the prefixURL of a File
// Manager object.
func (m *FileManager) SetPrefixURL(url string) {
	url = strings.TrimPrefix(url, "/")
	url = strings.TrimSuffix(url, "/")
	url = "/" + url
	m.prefixURL = strings.TrimSuffix(url, "/")
}

// SetBaseURL updates the baseURL of a File Manager
// object.
func (m *FileManager) SetBaseURL(url string) {
	url = strings.TrimPrefix(url, "/")
	url = strings.TrimSuffix(url, "/")
	url = "/" + url
	m.baseURL = strings.TrimSuffix(url, "/")
}

// SetScope updates a user scope and its virtual file system.
// If the user string is blank, it will change the base scope.
func (m *FileManager) SetScope(scope string, username string) error {
	var u *User

	if username == "" {
		u = m.User
	} else {
		var ok bool
		u, ok = m.Users[username]
		if !ok {
			return errors.New("Inexistent user")
		}
	}

	u.Scope = strings.TrimSuffix(scope, "/")
	u.fileSystem = webdav.Dir(u.Scope)

	return nil
}

// NewUser creates a new user on a File Manager struct
// which inherits its configuration from the main user.
func (m *FileManager) NewUser(username string) error {
	if _, ok := m.Users[username]; ok {
		return ErrDuplicated
	}

	m.Users[username] = &User{
		fileSystem:    m.User.fileSystem,
		Scope:         m.User.Scope,
		Rules:         m.User.Rules,
		AllowNew:      m.User.AllowNew,
		AllowEdit:     m.User.AllowEdit,
		AllowCommands: m.User.AllowCommands,
		Commands:      m.User.Commands,
	}

	return nil
}

// ServeHTTP determines if the request is for this plugin, and if all prerequisites are met.
func (m *FileManager) ServeHTTP(w http.ResponseWriter, r *http.Request) (int, error) {
	// TODO: Handle errors here and make it compatible with http.Handler
	return serveHTTP(&requestContext{
		fm: m,
		us: nil,
		fi: nil,
	}, w, r)
}

// Allowed checks if the user has permission to access a directory/file.
func (u User) Allowed(url string) bool {
	var rule *Rule
	i := len(u.Rules) - 1

	for i >= 0 {
		rule = u.Rules[i]

		if rule.Regex {
			if rule.Regexp.MatchString(url) {
				return rule.Allow
			}
		} else if strings.HasPrefix(url, rule.Path) {
			return rule.Allow
		}

		i--
	}

	return true
}
