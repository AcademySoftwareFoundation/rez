#ifndef HELLO_HPP
#define HELLO_HPP

#include <string>

#if defined(_MSC_VER)
#  define HELLO_API __declspec(dllexport)
#else
#  define HELLO_API [[gnu::visibility("default")]]
#endif

namespace hello
{
HELLO_API
auto say_hello() -> std::string;
} // namespace hello

#endif // HELLO_HPP
